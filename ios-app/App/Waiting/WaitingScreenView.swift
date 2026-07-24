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

    private var progress: Double {
        guard totalWait > 0 else { return 1 }
        return 1 - (remaining / totalWait)
    }

    var body: some View {
        VStack(spacing: Theme.spacing * 1.5) {
            Spacer()

            countdownRing

            GlassCard {
                Text(currentMessage.text)
                    .font(.body.weight(.medium))
                    .multilineTextAlignment(.center)
                    .id(currentMessage.text)
                    .transition(.opacity.combined(with: .scale(scale: 0.98)))
            }
            .padding(.horizontal, Theme.spacing)

            Spacer()

            if SessionState.overridesToday > 0 {
                AccountabilityPromptButton(overrideCount: SessionState.overridesToday)
                    .padding(.bottom, Theme.spacing)
            }
        }
        .ancreBackground()
        .onReceive(tick) { _ in
            guard remaining > 0 else { return }
            withAnimation(.linear(duration: 1)) {
                remaining -= 1
            }
            if remaining <= 0 {
                onWaitCompleted()
            }
        }
        .onReceive(messageRotation) { _ in
            withAnimation(.spring(response: 0.5, dampingFraction: 0.8)) {
                currentMessage = MessageBank.random()
            }
        }
    }

    private var countdownRing: some View {
        ZStack {
            Circle()
                .stroke(.quaternary, lineWidth: 14)

            Circle()
                .trim(from: 0, to: progress)
                .stroke(
                    Theme.accentGradient,
                    style: StrokeStyle(lineWidth: 14, lineCap: .round)
                )
                .rotationEffect(.degrees(-90))
                .animation(.easeInOut(duration: 1), value: progress)

            Text(timeString(remaining))
                .font(.system(size: 44, weight: .bold, design: .rounded))
                .monospacedDigit()
                .contentTransition(.numericText())
        }
        .frame(width: 220, height: 220)
        .padding(.top, Theme.spacing)
    }

    private func timeString(_ interval: TimeInterval) -> String {
        let minutes = Int(interval) / 60
        let seconds = Int(interval) % 60
        return String(format: "%d:%02d", minutes, seconds)
    }
}
