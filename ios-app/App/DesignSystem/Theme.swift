import SwiftUI

/// Petit système de design partagé par tous les écrans, pensé pour le langage
/// visuel translucide/matériaux introduit par Apple à partir d'iOS 26
/// ("Liquid Glass") : surfaces en verre dépoli, profondeur, dégradés doux
/// plutôt que des aplats de couleur. Non prévisualisable ici (pas de
/// simulateur iOS disponible dans cet environnement) — à ajuster à l'œil
/// une fois ouvert dans Xcode.
enum Theme {
    static let accentGradient = LinearGradient(
        colors: [Color.indigo, Color.purple, Color.blue],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
    )

    static let backgroundGradient = LinearGradient(
        colors: [Color(.systemBackground), Color.indigo.opacity(0.08)],
        startPoint: .top,
        endPoint: .bottom
    )

    static let cardCornerRadius: CGFloat = 24
    static let controlCornerRadius: CGFloat = 16
    static let spacing: CGFloat = 20
}

/// Carte en verre dépoli réutilisable : matériau système + léger contour,
/// plutôt qu'un fond opaque classique.
struct GlassCard<Content: View>: View {
    @ViewBuilder let content: Content

    var body: some View {
        content
            .padding(Theme.spacing)
            .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: Theme.cardCornerRadius, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: Theme.cardCornerRadius, style: .continuous)
                    .strokeBorder(.white.opacity(0.15), lineWidth: 1)
            )
    }
}

/// Style de bouton principal : dégradé + retour haptique léger, cohérent
/// sur tous les CTA de l'app (valider, continuer, j'en ai vraiment besoin...).
struct PrimaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .foregroundStyle(.white)
            .padding(.vertical, 14)
            .frame(maxWidth: .infinity)
            .background(Theme.accentGradient, in: RoundedRectangle(cornerRadius: Theme.controlCornerRadius, style: .continuous))
            .scaleEffect(configuration.isPressed ? 0.97 : 1)
            .animation(.spring(response: 0.3, dampingFraction: 0.6), value: configuration.isPressed)
            .onChange(of: configuration.isPressed) { _, isPressed in
                if isPressed {
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                }
            }
    }
}

extension View {
    func ancreBackground() -> some View {
        self.background(Theme.backgroundGradient.ignoresSafeArea())
    }
}
