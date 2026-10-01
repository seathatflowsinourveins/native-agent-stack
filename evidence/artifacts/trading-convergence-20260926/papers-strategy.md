PAPERS: 25 verified

“Verified” means I opened a primary paper, author manuscript, or publisher text. White and Beaver were accessible only as abstracts; their missing details are identified below. Three additional papers remain unverified. Where a DOI/SSRN link failed, I give both that identifier and the manuscript actually opened.

The core JSON currently says “draft_pending_independent_pre_outcome_review” and “frozen_before_outcomes”: false. It retains H1—MAX conditioning—and H3—overnight versus intraday returns. H2, including filing/catalyst conditioning, is deferred to v3.1+. “Already cited” below refers specifically to protocol-core-draft.json, not merely the README.

My principal finding: none of the opened papers establishes executable, cost-net, point-in-time early entry into +50% to +200% US single-day movers. The useful evidence concerns conditional continuation/reversal, measurement quality, and study design. Reported return results below should not be interpreted as returns after your execution costs.

Verified papers:

1. Bali, Turan G., Nusret Cakici, and Robert F. Whitelaw. 2011. “Maxing Out: Stocks as Lotteries and the Cross-Section of Expected Returns.” Journal of Financial Economics 99(2): 427–446.

Sample: NYSE, AMEX, and Nasdaq stocks, July 1962–December 2005; monthly portfolios sorted on the preceding month’s maximum daily return.
Result: highest-minus-lowest MAX deciles earn −1.03% per month, value weighted; four-factor alpha is −1.18% per month. This is a monthly cross-sectional result, not a five-day forecast following an extreme event.
Already cited: YES, as BCW 2011.
Informs: H1’s relative-return hypothesis; does not establish profitable absolute returns for the low-MAX long leg.
Sources: [DOI, resolver unavailable](https://doi.org/10.1016/j.jfineco.2010.08.014); [opened author manuscript](https://pages.stern.nyu.edu/~rwhitela/papers/max%20jfe.pdf).

2. Zawadowski, A. G., J. Kertész, and G. Andor. 2004. “Large Price Changes on Small Scales.” arXiv:cond-mat/0401055.

Sample: liquid NYSE and Nasdaq stocks, 2000–2002; extreme 15-minute changes selected using absolute and volatility-relative thresholds, including an absolute 4% threshold.
Result: approximately 1% reversal occurs within 10–30 minutes. Liquidity deterioration differs sharply between the exchanges.
Already cited: NO.
Informs: a future intraday reversal/exit arm with contemporaneous spread measurements. The event scale, market structure, and liquid-stock selection differ substantially from modern +50% to +200% microcap movers.
Source: [opened arXiv paper](https://arxiv.org/abs/cond-mat/0401055).

3. Savor, Pavel G. 2012. “Stock Returns after Major Price Shocks: The Impact of Information.” Journal of Financial Economics 106(3): 635–659.

Sample: US CRSP stocks, 1995–2009, with substantial analyst coverage; 166,470 firm-days with absolute abnormal returns exceeding 10%.
Result: information-associated shocks exhibit continuation; other shocks reverse. A combined strategy with a 20-day holding period reports 35.3% annualized abnormal returns, before establishing your execution feasibility.
Critical PIT limitation: the information classification permits analyst reports from day −1 through day +1.
Already cited: NO.
Informs: deferred H2 and a future catalyst-by-direction arm. Rebuild labels using information available at the decision timestamp; do not import its retrospective classification.
Sources: [DOI, resolver unavailable](https://doi.org/10.1016/j.jfineco.2012.06.011); [opened author manuscript](https://faculty.wharton.upenn.edu/wp-content/uploads/2012/10/Stock-Returns-After-Major-Price-Shocks---May-2012---Final.pdf).

4. Lou, Dong, Christopher Polk, and Spyros Skouras. 2019. “A Tug of War: Overnight versus Intraday Expected Returns.” Journal of Financial Economics 134(1): 192–213.

Sample: US CRSP/Compustat/TAQ stocks, 1993–2013; excludes prices below $5 and the smallest NYSE size quintile.
Result: across 14 strategies, expected profits concentrate in particular overnight or intraday components. A one-standard-deviation increase in their tug-of-war measure predicts approximately one percentage point greater next-month strategy return.
Measurement: the main opening-price measure uses first-half-hour VWAP, not simply the official opening print.
Already cited: YES, LPS 2019.
Informs: H3, especially the distinction between an economic decomposition and a replication of the paper’s measurement.
Sources: [DOI, resolver unavailable](https://doi.org/10.1016/j.jfineco.2019.03.011); [opened March 2018 manuscript](https://eprints.lse.ac.uk/87481/7/Polk_Tug%20of%20War.pdf).

5. Akbas, Ferhat, Ekkehart Boehmer, Chao Jiang, and Paul D. Koch. 2022. “Overnight Returns, Daytime Reversals, and Future Stock Returns.” Journal of Financial Economics 145(3): 850–875.

Sample: US common stocks, May 1993–December 2017; prices above $1, excluding financials and utilities. Small stocks are included.
Result: high-minus-low frequency of positive-overnight/negative-daytime reversals predicts approximately +0.92% next-month equal-weighted return; four-factor alpha is +0.81%.
Already cited: YES, ABJK 2022.
Informs: H3 and a future reversal-frequency conditioning arm. It directly corrects the protocol’s description of this sample as “large, liquid names.”
Sources: [DOI, resolver unavailable](https://doi.org/10.1016/j.jfineco.2021.09.019); [opened September 2021 manuscript](https://assets.super.so/<uuid>/files/<uuid>.pdf).

6. Berkman, Henk, Paul D. Koch, Laura Tuttle, and Ying Jenny Zhang. 2012. “Paying Attention: Overnight Returns and the Hidden Cost of Buying at the Open.” Journal of Financial and Quantitative Analysis 47(4): 715–741.

Sample: approximately the largest 3,000 US stocks, 1996–2008.
Result: midpoint-based average overnight returns are approximately +10 basis points daily, versus −7 basis points intraday. Opening-price pressure is stronger in attention-attracting stocks; buying near the open can impose costs exceeding the effective half-spread.
Already cited: NO.
Informs: H3 entry timing and a future opening-window sensitivity study. Overnight appreciation cannot automatically be captured by buying after the opening pressure has occurred.
Sources: [DOI, resolver unavailable](https://doi.org/10.1017/S0022109012000270); [opened journal-paper copy](https://scispace.com/pdf/paying-attention-overnight-returns-and-the-hidden-cost-of-52o3bohkjq.pdf).

7. Barber, Brad M., Xing Huang, Terrance Odean, and Christopher Schwarz. 2022. “Attention-Induced Trading and Returns: Evidence from Robinhood Users.” Journal of Finance 77(6): 3141–3190.

Sample: US stocks held by Robinhood users, May 2018–August 2020.
Result: the most intensely purchased stocks subsequently earn −4.7% abnormal returns over 20 days. At the extreme threshold of a 750% increase in holders, 45 events average −19.6% subsequent abnormal returns. Effects concentrate in stocks below $1 billion market capitalization.
Already cited: NO in the core JSON; YES in the README.
Informs: deferred H2 attention intensity, small-cap interactions, and post-attention reversal. These are ownership-growth thresholds, not equivalent stock-return thresholds.
Sources: [opened publisher DOI page](https://onlinelibrary.wiley.com/doi/10.1111/jofi.13183); [opened paper extract](https://pdfhost.io/fr-FR/v/7XVyGQI8W_The_Journal_of_Finance_-_2022_-_BARBER_-_Attention%E2%80%90Induced_Trading_and_Returns_Evidence_from_Robinhood_Users__2_).

8. Boehmer, Ekkehart, Charles M. Jones, Xiaoyan Zhang, and Xinran Zhang. 2021. “Tracking Retail Investor Activity.” Journal of Finance 76(5): 2249–2305.

Sample: US common stocks priced at least $1, 2010–2015; approximately 3,000 stocks daily, using off-exchange subpenny executions to identify marketable retail orders.
Result: stocks with net retail buying outperform those with net selling by approximately 10 basis points over the following week.
Already cited: NO.
Informs: a future preceding-order-flow arm. Its identification algorithm requires qualification using papers 9 and 10 before adoption.
Sources: [opened publisher DOI page](https://onlinelibrary.wiley.com/doi/10.1111/jofi.13033); [opened journal paper](https://www.pbcsf.tsinghua.edu.cn/__local/4/54/C2/14F447AB4BFAB3483114AC602DA_F576AF2B_107C91.pdf?e=.pdf).

9. Barber, Brad M., Xing Huang, Philippe Jorion, Terrance Odean, and Christopher Schwarz. 2024. “A (Sub)penny for Your Thoughts: Tracking Retail Investor Activity in TAQ.” Journal of Finance 79(4): 2403–2427.

Sample: approximately 85,000 actual US-equity trades through six accounts at five brokers, December 2021–June 2022; the main experiment contains approximately 64,000 trades with 128 stocks selected daily through stratification.
Result: the older algorithm identifies 35% of trades and incorrectly signs 28% of those identified. Using quote midpoints reduces signing errors to 5%; identification coverage remains incomplete.
Already cited: NO.
Informs: the measurement gate for any v3.1+ retail-order-flow signal, particularly in wide-spread movers.
Source: [opened publisher full text and DOI](https://onlinelibrary.wiley.com/doi/10.1111/jofi.13334).

10. Ardia, David, Clément Aymard, and Tolga Cenesizoglu. 2024. “Revisiting Boehmer et al. (2021): Recent Period, Alternative Method, Different Conclusions.” arXiv:2403.17095, version 1.

Sample: US common stocks, 2010–2021, comparing 2010–2015 with 2016–2021.
Result: estimated predictive persistence falls from approximately 6–8 weeks to four weeks. The aggregate long–short strategy ceases to be profitable in the later period, while predictability disappears for large-cap/high-price stocks and weakens elsewhere. Volume-based order-imbalance agreement between methods falls from approximately 0.68 to 0.44.
Already cited: NO.
Informs: future order-flow arms with frozen identification methods and explicit temporal replication.
Sources: [opened arXiv record](https://arxiv.org/abs/2403.17095); [opened version-1 full text](https://arxiv.org/html/2403.17095v1).

11. Campbell, John L., Brady J. Twedt, and Benjamin C. Whipple. 2021. “Trading Prior to the Disclosure of Material Information: Evidence from Regulation Fair Disclosure Form 8-Ks.” Contemporary Accounting Research 38(1): 412–442.

Sample: 28,924 Item 7.01 filings from 2,952 US firms, 2005–2013; stock prices at least $5, with EDGAR, TAQ, accounting data, and news.
Result: abnormal trading volume rises approximately 21% in the hour before disclosure. The authors check accompanying press releases to identify earlier public dissemination.
Already cited: NO.
Informs: deferred H2’s first-public-disclosure timestamp and a prospective pre-disclosure order-flow arm. Evidence for Item 7.01 does not establish an effect for proposed Item 1.01 signals.
Source: [opened publisher full text and DOI](https://onlinelibrary.wiley.com/doi/10.1111/1911-3846.12610).

12. Aït-Sahalia, Yacine, Chen Xu Li, and Chenxu Li. 2024, revised June 2025. “So Many Jumps, So Little News.” Working paper, SSRN 4897887; related NBER Working Paper 32746.

Sample: time-varying Dow Jones Industrial Average constituents, September 2003–December 2018; high-frequency trades and timestamped news.
Result: up to 85% of intraday jumps lack identifiable public news, whereas approximately 96% of overnight jumps are associated with news. News-related jumps exhibit greater persistence and less reversal.
Already cited: NO.
Informs: future H2 × H3 interactions separating news-linked overnight moves from intraday jumps. These are statistically detected jumps in large stocks, not a +50% daily-mover population.
Sources: [SSRN identifier, access blocked](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4897887); [opened June 2025 manuscript](https://www.conftool.org/cavalcade-asia-pacific-2025/index.php/Ait-Sahalia-So_Many_Jumps,_So_Little_News-257.pdf?filename=Ait-Sahalia-So_Many_Jumps,_So_Little_News-257.pdf&form_id=257&page=downloadPaper).

13. Bradley, Daniel, Jan Hanousek Jr., Russell Jame, and Zicheng Xiao. 2024. “Place Your Bets? The Value of Investment Research on Reddit’s Wallstreetbets.” Review of Financial Studies 37(5): 1409–1459.

Sample: US-stock discussions, July 2018–June 2021; 5,050 single-company due-diligence reports and 13,255 nonresearch posts.
Result: before the GameStop episode, an incremental buy recommendation predicts a 5.17-percentage-point increase in next-month returns; 2.33 points excluding GameStop and AMC. One-month predictability disappears afterward.
Already cited: NO.
Informs: deferred H2 social signals, separating substantive research from attention and requiring regime replication. Preserve original post versions and timestamps.
Sources: [DOI, resolver unavailable](https://doi.org/10.1093/rfs/hhad098); [opened October 2023 manuscript](https://russelljame.com/wsb_10_19_23.pdf).

14. Green, T. Clifton, and Russell Jame. 2026. “Retail Trading Frenzies and Real Investment.” April 2026 working-paper revision; SSRN 4874993.

Sample: US common stocks with CRSP, Compustat, and retail-flow measurements, 2007–2023.
Result: frenzy quarters exhibit approximately +22% abnormal returns, followed by nearly complete reversal over 24 months. The definition—three-month retail imbalance exceeding 2% of shares outstanding—identifies approximately 1.3% of firm-months.
Already cited: NO.
Informs: a future sustained-attention/issuance-risk arm and longer-horizon exits. The formation window is three months; this is not a demonstrated early intraday trigger.
Sources: [SSRN identifier, access blocked](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4874993); [opened April 2026 manuscript](https://russelljame.com/frenzies_april26.pdf).

15. Filimonov, Vladimir, and Didier Sornette. 2013. “A Stable and Robust Calibration Scheme of the Log-Periodic Power Law Model.” Physica A 392(17): 3698–3707.

Sample: methodological development with Shanghai Composite illustrations, January 2007–March 2008; no US individual-stock trading panel.
Result: the reformulation reduces calibration to three nonlinear parameters and improves the optimization surface. It does not report validated cost-net exit profitability.
Already cited: NO.
Informs: a future LPPLS exit experiment with rolling, strictly backward-looking fits and a preregistered comparison against fixed exits.
Source: [opened arXiv paper and journal citation](https://arxiv.org/abs/1108.0099).

16. Grobys, Klaus. 2026; published online October 2025. “Magnificent 7: Unsustainable Growth and Systemic Risk.” Review of Quantitative Finance and Accounting 67: 437–468.

Sample: seven US megacap stocks, daily prices from May 13, 2016, through January 17, 2025.
Result: four of seven exhibit significant LPPLS signatures; fitted regime-change windows fall between February and June 2025.
Already cited: NO.
Informs: a future LPPLS benchmark, with weak transfer to daily microcap blow-offs. The journal publication follows the forecast window, so this source alone does not establish prospectively registered forecasting or executable exit performance.
Sources: [DOI, resolver unavailable](https://doi.org/10.1007/s11156-025-01458-6); [opened publisher article](https://link.springer.com/article/10.1007/s11156-025-01458-6).

17. Busseti, Enzo, Ernest K. Ryu, and Stephen Boyd. 2016. “Risk-Constrained Kelly Gambling.” Journal of Investing 25(3): 118–134.

Sample: theoretical and synthetic betting distributions, including Monte Carlo wealth paths; no historical equity universe or market years.
Result: in one finite-outcome example, constraining risk reduces simulated probability of wealth falling below 70% of initial wealth from 39.7% to 7.3%, while expected log growth falls from 0.062 to 0.043 per period.
Already cited: NO.
Informs: future sizing after an independently established edge. Its distributional assumptions do not establish a safe leverage multiple for gap-prone, halted stocks.
Sources: [opened arXiv paper](https://arxiv.org/abs/1603.06183); [opened author publication record](https://web.stanford.edu/~boyd/papers/kelly.html).

18. White, Halbert. 2000. “A Reality Check for Data Snooping.” Econometrica 68(5): 1097–1126.

Sample: methodological time-series/model-comparison framework. Only the publisher abstract was accessible; application years and numerical tables were not verified.
Result: tests whether the best model found during a specification search has expected performance exceeding a benchmark—formally, a global null of no positive expected advantage. No numerical effect size is claimed here.
Already cited: NO.
Informs: future searches over many candidate rules, provided the tested search family and return histories are retained. It addresses a different question from testing five already specified hypotheses.
Source: [opened publisher DOI abstract](https://onlinelibrary.wiley.com/doi/10.1111/1468-0262.00152).

19. Romano, Joseph P., and Michael Wolf. 2005. “Stepwise Multiple Testing as Formalized Data Snooping.” Econometrica 73(4): 1237–1282.

Sample: theory, simulations, and an empirical illustration; one simulation uses 40 strategies, 100 observations, and 5,000 repetitions.
Result: the stepdown procedure asymptotically controls familywise error at the chosen alpha while exploiting dependence across tests; it can reject more false nulls than single-step procedures.
Already cited: NO.
Informs: a future larger, correlated hypothesis family. It is an alternative to preregister before results, not a reason to replace Holm after seeing unfavorable p-values.
Sources: [opened publisher DOI page](https://onlinelibrary.wiley.com/doi/10.1111/j.1468-0262.2005.00615.x); [opened full paper](https://www.econ.uzh.ch/dam/jcr:<uuid>/etca.pdf).

20. Benjamini, Yoav, and Daniel Yekutieli. 2001. “The Control of the False Discovery Rate in Multiple Testing under Dependency.” Annals of Statistics 29(4): 1165–1188.

Sample: mathematical results; no market, years, or stock universe.
Result: BH controls false discovery rate under specified positive dependence. For arbitrary dependence, the conservative adjustment replaces target q by q/H_m, where H_m = Σ(1/i).
Already cited: NO.
Informs: exploratory v3.1+ discovery families. FDR control is different from Holm’s familywise-error control and should not silently replace it. The original BH paper is from 1995, outside the requested publication interval.
Sources: [opened DOI landing page](https://doi.org/10.1214/aos/1013699998); [opened author manuscript](https://www.math.tau.ac.il/~ybenja/depApr27.pdf).

21. Bailey, David H., Jonathan M. Borwein, Marcos López de Prado, and Qiji Jim Zhu. 2017. “The Probability of Backtest Overfitting.” Journal of Computational Finance 20(4): 39–69.

Sample: mathematical framework and constructed investment-strategy examples; no single historical US-equity panel.
Result: in the opened manuscript’s illustration, all selected in-sample Sharpe ratios are positive, yet approximately 78% of corresponding out-of-sample Sharpe ratios are negative. CSCV estimates the probability that an in-sample winner ranks below the out-of-sample median.
Already cited: NO.
Informs: preserving the complete trial-return matrix for v1/v2 and future searches. A count of 1,012 attempted combinations alone cannot produce an honest PBO estimate.
Sources: [opened journal DOI page](https://doi.org/10.21314/JCF.2016.322); [opened author manuscript](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf).

22. Bailey, David H., and Marcos López de Prado. 2014. “The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality.” Journal of Portfolio Management 40(5): 94–107.

Sample: analytical results and synthetic examples, rather than a historical stock panel.
Result: an illustrative five-year strategy with annualized Sharpe 2.5 fails a 95% confidence criterion after adjustment; its deflated probability is approximately 0.90. The adjustment incorporates trial multiplicity, Sharpe dispersion, sample length, skewness, and kurtosis.
Already cited: NO.
Informs: a supplementary selection diagnostic for future strategy research. The 1,012 combinations should not automatically be treated as 1,012 independent trials.
Sources: [DOI, access blocked](https://doi.org/10.3905/jpm.2014.40.5.094); [opened author manuscript](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf).

23. Glasserman, Paul, and Caden Lin. 2023. “Assessing Look-Ahead Bias in Stock Return Predictions Generated by GPT Sentiment Analysis.” arXiv:2309.17322.

Sample: US stocks and news, 2015–2022; separate datasets include 129,431 headlines covering 6,723 firms and 181,908 Reuters headlines covering 678 S&P 500 firms.
Result: for Reuters headlines, anonymization changes mean daily long–short returns from 10.74 to 13.84 basis points in the earlier sample, and from 6.07 to 12.23 basis points afterward. These calculations omit important trading frictions.
Already cited: NO.
Informs: deferred H2 if historical news is scored by modern language models. Anonymization is a diagnostic, not proof that training-data leakage has been removed.
Sources: [opened arXiv record](https://arxiv.org/abs/2309.17322); [opened full text](https://arxiv.org/html/2309.17322v1).

24. Levy, Bradford. 2026. “Caution Ahead: Numerical Reasoning and Look-Ahead Bias in AI Models.” Journal of Accounting Research, early-view article.

Sample: US Compustat financial statements, 1968–2021; baseline of 30,210 firms and 346,731 firm-years, with sampled model experiments.
Result: net income and sales jointly identify more than 99.9% of annual earnings observations. GPT-4’s approximately 60% earnings-direction accuracy falls to approximately 51%, statistically indistinguishable from chance, after perturbing the least significant digit.
Already cited: NO.
Informs: any future LLM catalyst/fundamental arm. Removing company names does not necessarily remove historical identity or memorization.
Source: [opened DOI full text](https://doi.org/10.1111/1475-679x.70058).

25. Beaver, William H., Maureen F. McNichols, and Richard A. Price. 2007. “Delisting Returns and Their Effect on Accounting-Based Market Anomalies.” Journal of Accounting and Economics 43(2–3): 341–368.

Sample: US accounting-based anomaly portfolios incorporating delisting firm-years. Exact years and universe size were not available in the opened institutional abstract.
Result: including delistings increases measured returns for earnings, cash-flow, and book-to-market strategies, but decreases them for an accrual strategy. Numerical magnitudes remain unverified.
Already cited: NO.
Informs: universe and terminal-return acceptance across H1/H3. The direction of survivorship distortion cannot safely be presumed; retained missing-security and delisting cases need explicit treatment.
Sources: [DOI, resolver unavailable](https://doi.org/10.1016/j.jacceco.2006.12.002); [opened Stanford primary abstract](https://gsbpreserve.stanford.edu/view/34201/delisting-returns-and-their-effect-on-accounting-based-market-anomalies).

The following three papers remain unverified at paper-text level. Their identifiers were attempted but did not yield the paper; reported numbers are leads, not accepted evidence.

U1. Kapadia, Nishad, and Morad Zekhnini. 2019. “Do Idiosyncratic Jumps Matter?” Journal of Financial Economics 131(3): 666–692.

Sample: US individual stocks; exact years and eligibility rules unverified.
Reported result: a weekly rebalanced predicted-jump strategy reportedly earns 9.4% annualized raw return and 8.1% four-factor alpha. The author’s research page supports the broader finding that a typical stock’s annual return accrues over roughly four jump days, but I did not obtain the paper.
Already cited: NO.
Informs: a future ex-ante jump-probability entry arm, distinct from conditioning on realized MAX.
Sources: [DOI, unavailable](https://doi.org/10.1016/j.jfineco.2018.08.014); [opened author research page](https://sites.google.com/site/nishadkapadia42/).

U2. Hansen, Peter Reinhard. 2005. “A Test for Superior Predictive Ability.” Journal of Business & Economic Statistics 23(4): 365–380.

Sample: Monte Carlo experiments and US annual-inflation forecast comparisons; exact years unverified.
Reported result: studentization and a sample-dependent null improve power relative to White’s reality check when poor alternatives are present. Numerical rejection rates were not verified.
Already cited: NO.
Informs: SPA for a future broad rule search against a specified benchmark, with dependent resampling and the full candidate family retained.
Sources: [DOI, unavailable](https://doi.org/10.1198/073500105000000063); [SSRN manuscript link, blocked](https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID264569_code244328.pdf?abstractid=264569).

U3. Hou, Kewei, Chen Xue, and Lu Zhang. 2020. “Replicating Anomalies.” Review of Financial Studies 33(5): 2019–2133.

Sample: reported final study of 452 US-equity anomalies; reported period 1967–2016, not verified from opened full text.
Reported result: approximately 65% fail the conventional significance threshold; 82% fail a higher multiple-testing threshold. Earlier working papers have different counts, so versions must not be mixed.
Already cited: NO.
Informs: future replication standards, microcap concentration, weighting, and sensitivity to implementation choices.
Sources: [DOI, unavailable](https://doi.org/10.1093/rfs/hhy131); [author paper link, unavailable](https://theinvestmentcapm.com/uploads/1/2/2/6/122679606/houxuezhang2020rfs.pdf).

The five papers most likely to change the next preregistration, in priority order:

1. Akbas et al. 2022, paper 5. Correct the existing H3 literature description before freezing. Its small-stock inclusion and reversal-frequency conditioning are materially closer to the proposed population than the JSON acknowledges. Retain the two-sided mover hypothesis. [Source](https://assets.super.so/<uuid>/files/<uuid>.pdf)

2. Savor 2012, paper 3. Make information type a candidate explanation for continuation versus reversal. Its following-day analyst classification also supplies a concrete PIT failure to prohibit in a future H2 arm. [Source](https://faculty.wharton.upenn.edu/wp-content/uploads/2012/10/Stock-Returns-After-Major-Price-Shocks---May-2012---Final.pdf)

3. Campbell et al. 2021, paper 11. Define the catalyst timestamp as first public dissemination, including an earlier press release, rather than automatically SEC acceptance. Specify filing items separately: Item 7.01 evidence cannot stand in for Item 1.01 validation. [Source](https://onlinelibrary.wiley.com/doi/10.1111/1911-3846.12610)

4. Barber et al. 2024, paper 9. Freeze and qualify the retail-trade identification/signing method before any order-flow experiment. Its measured classification errors could change both estimated signals and conclusions about low-price, wide-spread stocks. [Source](https://onlinelibrary.wiley.com/doi/10.1111/jofi.13334)

5. Aït-Sahalia, Li, and Li, paper 12. Preregister a possible interaction between catalyst presence and overnight/intraday timing, rather than assuming one news mechanism across both. Its results motivate this distinction without establishing transport to extreme movers. [Source](https://www.conftool.org/cavalcade-asia-pacific-2025/index.php/Ait-Sahalia-So_Many_Jumps,_So_Little_News-257.pdf?filename=Ait-Sahalia-So_Many_Jumps,_So_Little_News-257.pdf&form_id=257&page=downloadPaper)

One direct protocol contradiction emerged; several other points are qualifications rather than refutations.

The direct contradiction is at [protocol-core-draft.json:65](blueprints/us-equities/mover-v3/protocol-core-draft.json:65):

“The literature (LPS 2019, ABJK 2022) concerns large, liquid names and gives no sign for movers, so the test is two-sided at every stage.”

ABJK includes small common stocks priced above $1; it is not restricted to large, liquid names. LPS does impose stronger price and size exclusions. Correct the shared sample characterization. The separate statement that these studies do not establish a sign for the exact mover population remains defensible. [ABJK source](https://assets.super.so/<uuid>/files/<uuid>.pdf)

Three qualifications should accompany the literature update:

- At [line 33](blueprints/us-equities/mover-v3/protocol-core-draft.json:33): “The 5-session b_lane arm is kept because it is the D horizon closest to BCW's holding period.” BCW establishes a monthly relative-return effect. Five sessions can remain a design choice, but neither its sign nor its magnitude is directly validated by BCW. Likewise, better relative performance of low MAX does not establish positive absolute cost-net returns. [BCW source](https://pages.stern.nyu.edu/~rwhitela/papers/max%20jfe.pdf)

- At [line 65](blueprints/us-equities/mover-v3/protocol-core-draft.json:65): “It uses official prints only, so it needs no fill and no cost model.” That is reasonable for the stated diagnostic. However, LPS’s principal opening measure is a 30-minute VWAP, so the official-print diagnostic should not be described as an exact replication of LPS. [LPS source](https://eprints.lse.ac.uk/87481/7/Polk_Tug%20of%20War.pdf)

- At [line 25](blueprints/us-equities/mover-v3/protocol-core-draft.json:25): “Holm runs over these five items only.” Nothing found makes this bounded family inherently wrong. It does mean its error-control claim applies to that family, not automatically to the preceding adaptive research history. Preserve the 1,012-trial history separately; use PBO/DSR only where their required data and assumptions are available. [PBO source](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf), [DSR source](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)

The LPPLS and sizing papers provide candidates for separately preregistered future experiments. They do not supply evidence requiring the present “No stops” and 1x equal-notional research specification to change.
