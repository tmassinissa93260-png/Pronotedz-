import SwiftUI

/// Point d'entrée du coach IA. Vérifie la disponibilité (iOS 26+ et
/// framework présent) avant de construire quoi que ce soit — sur un
/// appareil plus ancien, l'utilisateur voit un repli plutôt qu'un écran cassé.
struct CoachEntryView: View {
    let interestProfile: InterestProfile
    let overridesToday: Int

    var body: some View {
        #if canImport(FoundationModels)
        if #available(iOS 26.0, *) {
            CoachChatView(interestProfile: interestProfile, overridesToday: overridesToday)
        } else {
            CoachUnavailableView(reason: "Le coach IA nécessite iOS 26 ou plus récent.")
        }
        #else
        CoachUnavailableView(reason: "Le coach IA n'est pas disponible sur cette configuration.")
        #endif
    }
}

#if canImport(FoundationModels)
@available(iOS 26.0, *)
private struct CoachChatView: View {
    let interestProfile: InterestProfile
    let overridesToday: Int

    @State private var coach = CoachSession()
    @State private var draft = ""

    var body: some View {
        VStack(spacing: 0) {
            if let reason = coach.unavailabilityReason {
                CoachUnavailableView(reason: reason)
            } else {
                messageList
                inputBar
            }
        }
        .ancreBackground()
        .task {
            coach.start(interestProfile: interestProfile, overridesToday: overridesToday)
        }
    }

    private var messageList: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 12) {
                    ForEach(coach.messages) { message in
                        CoachBubble(message: message)
                            .id(message.id)
                    }
                    if coach.isResponding {
                        ProgressView()
                            .padding(.leading, Theme.spacing)
                    }
                }
                .padding(Theme.spacing)
            }
            .onChange(of: coach.messages.count) { _, _ in
                guard let last = coach.messages.last else { return }
                withAnimation { proxy.scrollTo(last.id, anchor: .bottom) }
            }
        }
    }

    private var inputBar: some View {
        HStack(spacing: 12) {
            TextField("Dis-lui ce qui se passe", text: $draft, axis: .vertical)
                .textFieldStyle(.plain)
                .padding(12)
                .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: Theme.controlCornerRadius, style: .continuous))

            Button {
                let text = draft
                draft = ""
                Task { await coach.send(text) }
            } label: {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.system(size: 32))
                    .foregroundStyle(Theme.accentGradient)
            }
            .disabled(draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || coach.isResponding)
        }
        .padding(Theme.spacing)
    }
}

@available(iOS 26.0, *)
private struct CoachBubble: View {
    let message: CoachMessage

    var body: some View {
        HStack {
            if message.role == .user { Spacer(minLength: 40) }

            Text(message.text)
                .padding(.vertical, 10)
                .padding(.horizontal, 14)
                .foregroundStyle(message.role == .user ? .white : .primary)
                .background {
                    if message.role == .user {
                        Theme.accentGradient
                    } else {
                        Rectangle().fill(.ultraThinMaterial)
                    }
                }
                .clipShape(RoundedRectangle(cornerRadius: Theme.controlCornerRadius, style: .continuous))

            if message.role == .coach { Spacer(minLength: 40) }
        }
    }
}
#endif

private struct CoachUnavailableView: View {
    let reason: String

    var body: some View {
        VStack(spacing: Theme.spacing) {
            Spacer()
            Image(systemName: "sparkles")
                .font(.system(size: 48))
                .foregroundStyle(.secondary)
            Text("Coach IA indisponible")
                .font(.headline)
            Text(reason)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, Theme.spacing)
            Spacer()
        }
        .ancreBackground()
    }
}
