import SwiftUI

/// Affiché à la place de WaitingScreenView quand SessionState.hasReachedDailyCapToday
/// est vrai — plus de compte à rebours possible, la seule sortie est une
/// demande envoyée au parent (voir TimeRequestSync.swift).
struct DailyLimitReachedView: View {
    let onExtraTimeGranted: () -> Void

    @State private var hasSentRequest = false
    @State private var isSending = false

    private var familyCode: String { ParentSettings.load().familyCode }

    var body: some View {
        VStack(spacing: Theme.spacing) {
            Spacer()

            Image(systemName: "hourglass.tophalf.filled")
                .font(.system(size: 48))
                .foregroundStyle(Theme.accentGradient)

            Text("Temps écran atteint pour aujourd'hui")
                .font(.system(.title2, design: .rounded, weight: .bold))
                .multilineTextAlignment(.center)

            Text("Tu peux demander un peu plus de temps à \(ParentSettings.load().parentName.isEmpty ? "tes parents" : ParentSettings.load().parentName).")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, Theme.spacing)

            if hasSentRequest {
                GlassCard {
                    Label("Demande envoyée, en attente de réponse...", systemImage: "clock")
                        .font(.subheadline)
                }
            } else {
                Button {
                    Task { await sendRequest() }
                } label: {
                    if isSending {
                        ProgressView().tint(.white)
                    } else {
                        Text("Demander 30 min de plus")
                    }
                }
                .buttonStyle(PrimaryButtonStyle())
                .padding(.horizontal, Theme.spacing)
                .disabled(isSending)
            }

            Spacer()
        }
        .padding(Theme.spacing)
        .ancreBackground()
        .task {
            // Repli explicite en l'absence de push CloudKit configuré (voir
            // TimeRequestSync.swift) : on vérifie nous-mêmes toutes les 30s
            // si le parent a répondu, tant que cet écran est affiché.
            await pollForApproval()
        }
    }

    private func sendRequest() async {
        isSending = true
        try? await TimeRequestSync.sendRequest(familyCode: familyCode, requestedMinutes: 30)
        isSending = false
        hasSentRequest = true
    }

    private func pollForApproval() async {
        while true {
            try? await Task.sleep(nanoseconds: 30_000_000_000)
            await TimeRequestSync.applyApprovedRequests(familyCode: familyCode)
            if !SessionState.hasReachedDailyCapToday {
                onExtraTimeGranted()
                break
            }
        }
    }
}
