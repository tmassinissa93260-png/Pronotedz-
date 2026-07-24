import SwiftUI

/// Questionnaire d'intérêts, rempli une fois à la première ouverture
/// (voir docs/concept-produit.md section 6ter). Volontairement court
/// (une seule question à choix multiple) pour ne pas décourager avant
/// même d'avoir commencé à utiliser l'app.
struct OnboardingQuestionnaire: View {
    @State private var selectedTags: Set<InterestTag> = []
    let onCompleted: () -> Void

    private let options: [(InterestTag, String)] = [
        (.lecture, "Lire (romans, essais, BD, presse)"),
        (.documentaire, "Regarder un documentaire"),
        (.sport, "Faire une activité physique"),
        (.sortieAccompagne, "Sortir avec quelqu'un"),
        (.sortieSeul, "Sortir seul(e)")
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text("Qu'est-ce qui te ferait dire non au scroll ?")
                .font(.title2.bold())
            Text("Sélectionne ce qui te tente, même vaguement. On s'en sert pour te proposer autre chose au bon moment.")
                .font(.subheadline)
                .foregroundStyle(.secondary)

            ForEach(options, id: \.0) { tag, label in
                Toggle(label, isOn: bindingFor(tag))
                    .toggleStyle(.button)
            }

            Button("Continuer") {
                var profile = InterestProfile.load()
                profile.tags = selectedTags
                profile.save()
                onCompleted()
            }
            .buttonStyle(.borderedProminent)
        }
        .padding()
    }

    private func bindingFor(_ tag: InterestTag) -> Binding<Bool> {
        Binding(
            get: { selectedTags.contains(tag) },
            set: { isOn in
                if isOn { selectedTags.insert(tag) } else { selectedTags.remove(tag) }
            }
        )
    }
}
