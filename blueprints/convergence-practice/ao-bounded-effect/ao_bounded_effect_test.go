package integration

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"strings"
	"testing"

	"github.com/aoagents/agent-orchestrator/backend/internal/domain"
	"github.com/aoagents/agent-orchestrator/backend/internal/ports"
)

// This locally authored qualification fixture is loaded into the unchanged
// vendor integration package with Go's supported -overlay option. It reuses
// newSCMFixture, failingSCMObservation and scmMessengerSpy from:
// OrchestratorInc/agent-orchestrator v0.13.5
// c95ae361eee48d33c2f443c6d2fe69c445f548a8
// backend/internal/integration/scm_observer_test.go
// SHA256 2f55eb4194e9a73722890f0941bda596c97620d9208d5b2716bc3efa84e02767.
// The provider input is synthetic and the receiver records messages; this does
// not run an agent or measure actual human intervention or provider savings.
func TestCC133502ZAOEffect(t *testing.T) {
	ctx := context.Background()
	const (
		branch  = "feat/x"
		prURL   = "https://github.com/octocat/hello/pull/42"
		headSHA = "deadbeef"
		logTail = "setup\nsetup\nFAILED: build broke\n"
	)
	input := struct {
		Branch      string                 `json:"branch"`
		Detected    ports.SCMPRObservation `json:"detected"`
		Observation ports.SCMObservation   `json:"observation"`
	}{
		Branch: branch,
		Detected: ports.SCMPRObservation{
			URL: prURL, Number: 42, SourceBranch: branch,
			HeadRepo: scmTestRepo.Repo, TargetBranch: "main",
			HeadSHA: headSHA, Author: "octocat",
		},
		Observation: failingSCMObservation(prURL, 42, headSHA, logTail),
	}
	inputBytes, err := json.Marshal(input)
	if err != nil {
		t.Fatalf("marshal fixed input envelope: %v", err)
	}
	inputDigest := sha256.Sum256(inputBytes)
	inputSHA256 := hex.EncodeToString(inputDigest[:])

	arms := []struct {
		name       string
		observe    bool
		policy     bool
		manual     bool
		wantSends  int
		wantPolls  int
		wantManual int
		source     string
	}{
		{"ao", true, true, false, 1, 2, 0, "native_ao_observer_lifecycle"},
		{"no_ao", false, true, true, 1, 0, 1, "explicit_simulated_manual_send"},
		{"ao_policy_disabled", true, false, false, 0, 2, 0, "none_policy_disabled"},
	}
	for _, arm := range arms {
		t.Run(arm.name, func(t *testing.T) {
			// Each arm starts with independently fresh upstream fixture state.
			f := newSCMFixture(t, input.Branch)
			f.provider.detected[input.Branch] = input.Detected
			f.provider.observations[42] = input.Observation
			if !arm.policy {
				updated, err := f.store.SetSessionAutoInjectCI(ctx, f.session.ID, false, f.now)
				if err != nil || !updated {
					t.Fatalf("SetSessionAutoInjectCI(false): updated=%v err=%v", updated, err)
				}
			}

			polls, manualSends := 0, 0
			var firstSignature, secondSignature string
			if arm.observe {
				for i := 0; i < 2; i++ {
					polls++
					if err := f.observer.Poll(ctx); err != nil {
						t.Fatalf("Poll %d: %v", polls, err)
					}
					signature, err := f.store.GetPRLastNudgeSignature(ctx, prURL)
					if err != nil {
						t.Fatalf("GetPRLastNudgeSignature after Poll %d: %v", polls, err)
					}
					if i == 0 {
						firstSignature = signature
						if got := f.spy.count(); got != arm.wantSends {
							t.Fatalf("recorder sends after first Poll=%d, want %d", got, arm.wantSends)
						}
					} else {
						secondSignature = signature
					}
				}
				if firstSignature != secondSignature {
					t.Fatalf("second identical Poll changed persisted dedup signature: before=%q after=%q", firstSignature, secondSignature)
				}
				if arm.policy && firstSignature == "" {
					t.Fatal("native AO send did not persist its dedup signature")
				}
				if !arm.policy && firstSignature != "" {
					t.Fatal("policy-disabled inverse acknowledged an unsent notification")
				}
			}
			if arm.manual {
				// The observer is bypassed entirely. This explicit action is a
				// simulated manual delivery to the same upstream recorder type.
				body := "CI is failing for PR 42.\nFailed check: build\nPR: " + prURL + "\n" + input.Observation.CI.FailureLogTail
				manualSends++
				if err := f.spy.Send(ctx, f.session.ID, body); err != nil {
					t.Fatalf("simulated manual Send: %v", err)
				}
			}

			pr, found, err := f.store.GetPR(ctx, prURL)
			if err != nil {
				t.Fatalf("GetPR: %v", err)
			}
			checks, err := f.store.ListChecks(ctx, prURL)
			if err != nil {
				t.Fatalf("ListChecks: %v", err)
			}
			if arm.observe {
				if !found || pr.SessionID != f.session.ID || pr.Number != 42 || pr.HeadSHA != headSHA || pr.CI != domain.CIFailing {
					t.Fatalf("persisted native PR identity/CI mismatch: found=%v row=%+v", found, pr)
				}
				if len(checks) != 1 || checks[0].Name != "build" || checks[0].Status != domain.PRCheckFailed || checks[0].CommitHash != headSHA || checks[0].LogTail != logTail {
					t.Fatalf("persisted native failed-check mismatch: %+v", checks)
				}
			} else if found || len(checks) != 0 {
				t.Fatalf("observer-bypassed arm wrote PR/check state: found=%v checks=%d", found, len(checks))
			}

			messages := f.spy.snapshot()
			if len(messages) != arm.wantSends || polls != arm.wantPolls || manualSends != arm.wantManual {
				t.Fatalf("counts: recorder=%d polls=%d manual=%d, want %d/%d/%d", len(messages), polls, manualSends, arm.wantSends, arm.wantPolls, arm.wantManual)
			}
			receivedFailureInfo := false
			if arm.wantSends == 1 {
				msg := messages[0]
				receivedFailureInfo = msg.session == f.session.ID && strings.Contains(msg.body, "CI is failing") && strings.Contains(msg.body, prURL) && strings.Contains(msg.body, "build") && strings.Contains(msg.body, logTail)
				if !receivedFailureInfo {
					t.Fatalf("receiver missing same relevant CI failure information: %q", msg.body)
				}
			}
			observation := struct {
				Arm                     string `json:"arm"`
				Evidence                string `json:"evidence"`
				InputSHA256             string `json:"input_sha256"`
				ObserverPolls           int    `json:"observer_polls"`
				RecorderSends           int    `json:"recorder_sends"`
				ManualSends             int    `json:"simulated_manual_sends"`
				NotificationSource      string `json:"notification_source"`
				ExpectedHeadSHA         string `json:"expected_head_sha"`
				ExpectedFailedCheck     string `json:"expected_failed_check"`
				PersistedPR             bool   `json:"persisted_pr"`
				PersistedHeadSHA        string `json:"persisted_head_sha"`
				PersistedChecks         int    `json:"persisted_checks"`
				ReceivedSameFailureInfo bool   `json:"received_same_failure_info"`
				DedupSignaturePersisted bool   `json:"dedup_signature_persisted"`
				DedupSignatureStable    bool   `json:"dedup_signature_stable_after_second_poll"`
			}{
				Arm: arm.name, Evidence: "locally_authored_integration_synthetic_stimulus_recording_receiver",
				InputSHA256: inputSHA256, ObserverPolls: polls, RecorderSends: len(messages),
				ManualSends: manualSends, NotificationSource: arm.source,
				ExpectedHeadSHA: headSHA, ExpectedFailedCheck: "build",
				PersistedPR: found, PersistedHeadSHA: pr.HeadSHA, PersistedChecks: len(checks),
				ReceivedSameFailureInfo: receivedFailureInfo,
				DedupSignaturePersisted: firstSignature != "",
				DedupSignatureStable:    firstSignature != "" && firstSignature == secondSignature,
			}
			encoded, err := json.Marshal(observation)
			if err != nil {
				t.Fatalf("marshal arm observation: %v", err)
			}
			t.Log("CC133502Z_AO_EFFECT " + string(encoded))
		})
	}
}
