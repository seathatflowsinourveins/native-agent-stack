"""Supported native orders plus a separately labelled frozen LEAN policy.

rc5 engine.rs:1977-2006 settles -> modules -> settles; exchange.rs:1647-1690
collects process results before posting adjustments and acknowledging modules.
The final +1ns alert is an observation handshake, not a rewritten fill time.
"""
from decimal import Decimal


def build_observer(get_strategy):
    from nautilus_trader.backtest import SimulationModule

    class LeanPolicyObserver(SimulationModule):
        def __init__(self):
            super().__init__()
            self.pending = None
            self.errors = []
            self.acknowledgements = []

        def process(self, ts_now, context):
            if self.errors:
                raise ValueError('observer_failed:' + ';'.join(self.errors))
            if self.pending is not None:
                raise ValueError('observer_missing_acknowledgement')
            self.pending = int(ts_now)
            # Completed([]) requests acknowledge after the earlier distribution
            # adjustment has posted. It never adjusts cash or margin itself.
            return []

        def acknowledge(self, outcomes):
            if self.pending is None:
                raise ValueError('observer_duplicate_or_missing_acknowledgement')
            ts_now = self.pending
            self.pending = None
            try:
                if list(outcomes):
                    raise ValueError('observer_unexpected_adjustment_outcome')
                get_strategy().after_module_ack(ts_now)
                self.acknowledgements.append(ts_now)
            except BaseException as error:
                self.errors.append(type(error).__name__ + ':' + str(error))
                raise

        def reset(self):
            if self.pending is not None:
                raise ValueError('observer_pending_on_reset')

    return LeanPolicyObserver()


def build_strategy(fixture, policy, distribution, equity_id, venue, usd, bar_type, rows, case,
                   ex_instants_ns=(), price_precision=6):
    from nautilus_trader.model import ClientOrderId, OrderSide, Quantity, TimeInForce
    Base = fixture.build_strategy(equity_id, bar_type, rows, case, ex_instants_ns,
                                  price_precision=price_precision)

    class SixCaseFixture(Base):
        def __init__(self):
            super().__init__()
            self.phase = policy.SettlementHandshake()
            self.adaptive = policy.AdaptiveState(Decimal(case['initial_cash_usd']), case['adaptive'])
            self.pending_row = None
            self.marks = []
            self.margin_calls = []
            self.margin_warnings = []
            self.phase_alerts_registered = []
            self.phase_alerts_fired = []
            self.native_callback_events = []
            self.applied_distributions = set()
            self.entered = self.exited = False

        def _handle_bar(self, bar):
            if self.pending_row is not None:
                raise ValueError('previous_bar_observation_missing')
            index = self.bars_seen
            if index >= len(rows) or int(bar.ts_event) != rows[index]['ts_event_ns']:
                raise ValueError('six_bar_stream_desync')
            row = rows[index]
            if Decimal(str(bar.close)) != Decimal(row['c']):
                raise ValueError('six_bar_close_mismatch')
            self.bars_seen += 1
            self.pending_row = row

        def native_state(self):
            positions = self.cache.positions_open(instrument_id=equity_id)
            quantity = sum((Decimal(str(p.signed_qty)) for p in positions), Decimal(0))
            if quantity != self.position or quantity != quantity.to_integral_value():
                raise ValueError('native_position_does_not_match_fills')
            account = self.cache.account_for_venue(venue)
            if account is None:
                raise ValueError('native_account_missing')
            def money(value):
                return str(Decimal(str(value).split()[0])) if value is not None else '0'
            return {'quantity': int(quantity), 'native_balance_total': money(account.balance_total(usd)),
                    'native_balance_free': money(account.balance_free(usd)),
                    'native_initial_margin': money(account.initial_margin(equity_id)),
                    'native_maintenance_diagnostic': money(account.maintenance_margin(equity_id))}

        def _sync_distributions(self, ts_now):
            ledger = fixture.posted_distribution_ledger(distribution.emissions,
                                                        distribution.acknowledgements)
            for item in ledger:
                if item['ex_date'] in self.applied_distributions:
                    continue
                if not item['engine_posted'] or item['utc_seconds'] * 10**9 > ts_now:
                    raise ValueError('distribution_not_settled_before_policy')
                self.cash += Decimal(item['amount'])
                self.applied_distributions.add(item['ex_date'])

        def after_module_ack(self, ts_now):
            self._sync_distributions(ts_now)
            row = self.pending_row
            if row is None or row['ts_event_ns'] != ts_now:
                return
            snapshot = self.native_state()
            observe_ns = self.phase.begin(ts_now, snapshot['quantity'])
            price = Decimal(row['c'])
            equity = self.cash + self.position * price
            # Native historical regular-session membership is hash-bound. The
            # exchange is closed at the last completed bar, including 13:00
            # short sessions; future price values are never inspected.
            index = self.bars_seen - 1
            exchange_open = (index + 1 < len(rows)
                             and rows[index + 1]['session_date'] == row['session_date'])
            decision = policy.margin_decision(snapshot['quantity'], price, equity,
                                              Decimal(case['fee_usd']), exchange_open)
            if decision['quantity']:
                self.order_ref += 1
                ref = self.order_ref
                self.phase.expect_fill(ref, decision['quantity'])
                self.margin_calls.append({'kind': 'margin_call', 'utc_seconds': ts_now // 10**9,
                                          'economic_ts_event_ns': ts_now,
                                          'request_clock_ns': self.clock.timestamp_ns(), 'count': 1,
                                          'equity': str(equity),
                                          'margin_remaining': decision['policy_margin_remaining'],
                                          'quantity': decision['quantity'], 'order_ref': ref,
                                          'authority': 'frozen_LEAN_fixture_policy'})
                self._submit_market(ref, decision['quantity'], row, reduce_only=True)
            elif decision['warning']:
                self.margin_warnings.append({'kind': 'margin_warning', 'utc_seconds': ts_now // 10**9,
                                             'equity': str(equity),
                                             'margin_remaining': decision['policy_margin_remaining']})
            name = 'policy_observation_' + str(ts_now)
            self.clock.set_time_alert_ns(name, observe_ns, self._on_observation, allow_past=False)
            self.phase_alerts_registered.append({'name': name, 'alert_time_ns': observe_ns,
                                                  'economic_ts_event_ns': ts_now})

        def _on_observation(self, event):
            try:
                row = self.pending_row
                if row is None:
                    raise ValueError('duplicate_or_missing_observation_row')
                if str(event.name) != 'policy_observation_' + str(row['ts_event_ns']):
                    raise ValueError('observation_alert_name')
                snapshot = self.native_state()
                timing = self.phase.complete(int(event.ts_event), snapshot['quantity'])
                price = Decimal(row['c'])
                equity = self.cash + self.position * price
                completed = row['local_start'] == '15:00'
                observed = self.adaptive.observe(equity, completed_close=completed,
                     invested=self.entered and not self.exited and self.position > 0
                     and row['session_date'] != case['exit_decision_date'])
                margin = self.position * price * Decimal('0.5')
                self.marks.append({'kind': 'mark', 'utc_seconds': row['ts_event_ns'] // 10**9,
                                   **timing, 'equity': str(equity), 'cash': str(self.cash),
                                   'quantity': str(self.position), 'price': str(price),
                                   'gross': str(abs(self.position * price) / equity if equity > 0 else -1),
                                   'margin_used': str(margin), 'margin_remaining': str(equity-margin),
                                   'peak': observed['peak'], 'drawdown': observed['drawdown'],
                                   'maintenance_authority': 'frozen_LEAN_fixture_policy', **snapshot})
                self.phase_alerts_fired.append({'name': str(event.name), 'ts_event_ns': int(event.ts_event)})
                if completed:
                    index = self.bars_seen - 1
                    if not self.entered and row['session_date'] == case['entry_decision_date']:
                        fixture.check_decision_bar_is_session_final(rows, index)
                        self.entered = True
                        self._intent(row, Decimal(case['target']), 'entry', equity)
                    elif self.entered and not case['reject'] and not self.exited and row['session_date'] == case['exit_decision_date']:
                        fixture.check_decision_bar_is_session_final(rows, index)
                        self.exited = True
                        self._intent(row, Decimal(0), 'exit', equity)
                    elif observed['reduce']:
                        fixture.check_decision_bar_is_session_final(rows, index)
                        self.latch_events.append({'kind':'reduction', 'utc_seconds':row['ts_event_ns']//10**9,
                                                  **timing, 'equity':str(equity),
                                                  'peak':observed['peak'], 'drawdown':observed['drawdown']})
                        self._intent(row, Decimal('0.5'), 'reduce', equity)
                self.pending_row = None
            except BaseException as error:
                self._record('policy_observation', error)
                raise

        def _on_ex_date_alert(self, event):
            try:
                super()._on_ex_date_alert(event)
            except BaseException as error:
                self._record('ex_date_alert', error)
                raise

        def _intent(self, row, target, reason, equity):
            wanted = fixture.target_quantity(equity, target, Decimal(case['sizing_buffer']), Decimal(row['c']))
            delta = int(Decimal(wanted) - self.position)
            if not delta:
                raise ValueError('six_expected_nonzero_discretionary_intent')
            self.order_ref += 1
            self.intents.append({'kind':'intent', 'order_ref':self.order_ref,
                                 'utc_seconds':row['ts_event_ns']//10**9,
                                 'economic_ts_event_ns':row['ts_event_ns'],
                                 'decision_clock_ns':self.clock.timestamp_ns(),
                                 'quantity':delta, 'target':str(target), 'reason':reason,
                                 'decision_price':row['c'], 'decision_equity':str(equity)})
            if case['reject']:
                self._submit_market(self.order_ref, delta, row, reduce_only=False)
            else:
                self._submit_oco(self.order_ref, delta, Decimal(row['c']), row)

        def _submit_market(self, ref, quantity, row, *, reduce_only):
            side = OrderSide.BUY if quantity > 0 else OrderSide.SELL
            order = self.order_factory.market(instrument_id=equity_id, order_side=side,
                                             quantity=Quantity.from_int(abs(quantity)),
                                             time_in_force=TimeInForce.DAY, reduce_only=reduce_only,
                                             quote_quantity=False, client_order_id=ClientOrderId('SPY-POLICY-'+str(ref)))
            self.submitted[str(order.client_order_id)] = {'order_ref':ref, 'leg':'MARKET',
                 'order_list_id':None, 'trigger_price':None, 'submitted_session':row['session_date'],
                 'submitted_ts_event_ns':row['ts_event_ns']}
            self.submit_order(order)

        def _handle_order_event(self, event):
            self.native_callback_events.append(event.to_dict())
            before = len(self.fills)
            super()._handle_order_event(event)
            if len(self.fills) > before and self.fills[-1]['leg'] == 'MARKET':
                fill = self.fills[-1]
                fill['fill_source'] = 'native_market_LEAN_fixture_policy'
                self.phase.fill(fill['order_ref'], fill['quantity'], fill['ts_event_ns'])

    return SixCaseFixture
