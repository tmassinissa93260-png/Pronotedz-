import SwiftUI

/// Écran d'attente réel (30s ou 2min selon SessionState.requiredWait) — c'est
/// ici, dans l'app, que vit le compte à rebours et la rotation de messages,
/// puisque l'écran système de blocage ne peut pas les afficher (cf. section
/// 6bis du concept). Ouvert depuis ShieldActionExtension via l'URL scheme.
struct WaitingScreenView: View {
    let totalWait: TimeInterval
    let onWaitCompleted: () -> Void

    @State private var remaining: TimeInterval
    @State private var currentMessage = MessageBank.random()

    private let tick = Timer.publish(every: 1, on: .main, in: .common).autoconnect()
    private let messageRotation = Timer.publish(every: 6, on: .main, in: .common).autoconnect()

    init(totalWait: TimeInterval, onWaitCompleted: @escaping () -> Void) {
        self.totalWait = totalWait
        self.onWaitCompleted = onWaitCompleted
        _remaining = State(initialValue: totalWait)
    }

    var body: some View {
        VStack(spacing: 24) {
            Text(timeString(remaining))
                .font(.system(size: 48, weight: .bold, design: .rounded))
                .monospacedDigit()

            Text(currentMessage.text)
                .font(.body)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)
                .id(currentMessage.text)
                .transition(.opacity)
        }
        .onReceive(tick) { _ in
            guard remaining > 0 else { return }
            remaining -= 1
            if remaining <= 0 {
                onWaitCompleted()
            }
        }
        .onReceive(messageRotation) { _ in
            withAnimation { currentMessage = MessageBank.random() }
        }
    }

    private func timeString(_ interval: TimeInterval) -> String {
        let minutes = Int(interval) / 60
        let seconds = Int(interval) % 60
        return String(format: "%d:%02d", minutes, seconds)
    }
}
