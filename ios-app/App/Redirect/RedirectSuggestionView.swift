import SwiftUI

/// Affiché au retour dans l'app après le cooldown (voir concept-produit.md
/// section 6bis, étape 6). Propose des alternatives plutôt que de rouvrir
/// directement l'app surveillée, sans pour autant bloquer totalement l'accès
/// — une échappatoire existe toujours pour ne pas transformer l'app en prison.
struct RedirectSuggestionView: View {
    let suggestions: [Suggestion]
    let onContinueToApp: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text("Avant d'y retourner")
                .font(.title2.bold())

            ForEach(suggestions, id: \.title) { suggestion in
                VStack(alignment: .leading, spacing: 4) {
                    Text(suggestion.title).font(.headline)
                    Text(suggestion.description)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                .padding()
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12))
            }

            Button("Tu peux toujours scroller, mais...", action: onContinueToApp)
                .buttonStyle(.bordered)
                .font(.footnote)
        }
        .padding()
    }
}
