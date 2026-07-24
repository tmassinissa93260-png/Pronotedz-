import SwiftUI

/// Affiché au retour dans l'app après le cooldown (voir concept-produit.md
/// section 6bis, étape 6). Propose des alternatives plutôt que de rouvrir
/// directement l'app surveillée, sans pour autant bloquer totalement l'accès
/// — une échappatoire existe toujours pour ne pas transformer l'app en prison.
struct RedirectSuggestionView: View {
    let suggestions: [Suggestion]
    let onContinueToApp: () -> Void

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.spacing) {
                Spacer().frame(height: Theme.spacing / 2)

                Text("Avant d'y retourner")
                    .font(.system(.title, design: .rounded, weight: .bold))
                    .padding(.horizontal, Theme.spacing)

                ForEach(suggestions, id: \.title) { suggestion in
                    SuggestionCard(suggestion: suggestion)
                        .padding(.horizontal, Theme.spacing)
                }

                Button("Tu peux toujours scroller, mais...", action: onContinueToApp)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .padding(.top, Theme.spacing / 2)
                    .frame(maxWidth: .infinity)
            }
        }
        .ancreBackground()
    }
}

private struct SuggestionCard: View {
    let suggestion: Suggestion

    private var symbol: String {
        switch suggestion.tag {
        case .lecture: return "book.pages.fill"
        case .documentaire: return "play.rectangle.fill"
        case .sport: return "figure.run.circle.fill"
        case .sortieAccompagne: return "person.2.circle.fill"
        case .sortieSeul: return "figure.walk.circle.fill"
        }
    }

    var body: some View {
        GlassCard {
            HStack(alignment: .top, spacing: 14) {
                Image(systemName: symbol)
                    .font(.system(size: 30))
                    .foregroundStyle(Theme.accentGradient)

                VStack(alignment: .leading, spacing: 4) {
                    Text(suggestion.title).font(.headline)
                    Text(suggestion.description)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }

                Spacer(minLength: 0)
            }
        }
    }
}
