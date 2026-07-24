import SwiftUI

/// Questionnaire d'intérêts, rempli une fois à la première ouverture
/// (voir docs/concept-produit.md section 6ter). Volontairement court
/// (une seule question à choix multiple) pour ne pas décourager avant
/// même d'avoir commencé à utiliser l'app.
struct OnboardingQuestionnaire: View {
    @State private var selectedTags: Set<InterestTag> = []
    let onCompleted: () -> Void

    private let options: [(InterestTag, String, String)] = [
        (.lecture, "Lire", "book.fill"),
        (.documentaire, "Documentaire", "play.tv.fill"),
        (.sport, "Bouger", "figure.run"),
        (.sortieAccompagne, "Sortir accompagné(e)", "person.2.fill"),
        (.sortieSeul, "Sortir seul(e)", "figure.walk")
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.spacing) {
            Spacer().frame(height: Theme.spacing)

            Text("Qu'est-ce qui te ferait dire non au scroll ?")
                .font(.system(.title, design: .rounded, weight: .bold))

            Text("Sélectionne ce qui te tente, même vaguement. On s'en sert pour te proposer autre chose au bon moment.")
                .font(.subheadline)
                .foregroundStyle(.secondary)

            FlowChips(options: options, selectedTags: $selectedTags)

            Spacer()

            Button("Continuer") {
                var profile = InterestProfile.load()
                profile.tags = selectedTags
                profile.save()
                onCompleted()
            }
            .buttonStyle(PrimaryButtonStyle())
            .disabled(selectedTags.isEmpty)
            .opacity(selectedTags.isEmpty ? 0.5 : 1)
        }
        .padding(Theme.spacing)
        .ancreBackground()
    }
}

private struct FlowChips: View {
    let options: [(InterestTag, String, String)]
    @Binding var selectedTags: Set<InterestTag>

    private let columns = [GridItem(.adaptive(minimum: 150), spacing: 12)]

    var body: some View {
        LazyVGrid(columns: columns, alignment: .leading, spacing: 12) {
            ForEach(options, id: \.0) { tag, label, symbol in
                ChipToggle(
                    label: label,
                    symbol: symbol,
                    isSelected: selectedTags.contains(tag)
                ) {
                    withAnimation(.spring(response: 0.3, dampingFraction: 0.7)) {
                        if selectedTags.contains(tag) {
                            selectedTags.remove(tag)
                        } else {
                            selectedTags.insert(tag)
                        }
                    }
                }
            }
        }
    }
}

private struct ChipToggle: View {
    let label: String
    let symbol: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Label(label, systemImage: symbol)
                .font(.subheadline.weight(.medium))
                .padding(.vertical, 12)
                .padding(.horizontal, 16)
                .frame(maxWidth: .infinity)
                .foregroundStyle(isSelected ? .white : .primary)
                .background {
                    if isSelected {
                        Theme.accentGradient
                    } else {
                        Rectangle().fill(.ultraThinMaterial)
                    }
                }
                .clipShape(RoundedRectangle(cornerRadius: Theme.controlCornerRadius, style: .continuous))
        }
        .buttonStyle(.plain)
    }
}
