import SwiftUI

/// Tout premier écran de l'app, avant même le questionnaire d'intérêts :
/// détermine si les restrictions s'appliquent à l'utilisateur lui-même ou
/// à un enfant. Ce choix conditionne trois choses en aval (voir chaque
/// fichier concerné) : le type d'autorisation Screen Time demandée, le
/// destinataire du "témoin" (fixé par le parent plutôt que choisi librement),
/// et la désactivation par défaut du coach IA.
struct RoleSelectionView: View {
    let onSelected: (UserRole) -> Void

    @State private var isTeacherDashboardPresented = false
    @State private var isParentRemotePresented = false

    var body: some View {
        VStack(spacing: Theme.spacing) {
            Spacer()

            Text("Ancre")
                .font(.system(.largeTitle, design: .rounded, weight: .bold))
                .foregroundStyle(Theme.accentGradient)

            Text("C'est pour qui ?")
                .font(.title3.weight(.medium))
                .foregroundStyle(.secondary)

            RoleCard(
                title: "Moi-même",
                subtitle: "Je m'auto-restreins. Je peux toujours désinstaller l'app si je change d'avis.",
                symbol: "person.fill"
            ) {
                onSelected(.myself)
            }

            RoleCard(
                title: "Mon enfant",
                subtitle: "Les restrictions sont verrouillées par le code Temps d'écran — voir la note ci-dessous avant de continuer.",
                symbol: "figure.2.and.child.holdinghands"
            ) {
                onSelected(.child)
            }

            GlassCard {
                Label(
                    "Mode « Mon enfant » : nécessite un enfant déjà configuré dans le Partage familial Apple, sur son propre appareil. À faire avant de continuer si ce n'est pas déjà en place.",
                    systemImage: "info.circle"
                )
                .font(.caption)
                .foregroundStyle(.secondary)
            }

            Button("Je suis enseignant(e) — voir les stats de ma classe") {
                isTeacherDashboardPresented = true
            }
            .font(.footnote)
            .foregroundStyle(.secondary)

            Button("Je veux suivre mon enfant à distance") {
                isParentRemotePresented = true
            }
            .font(.footnote)
            .foregroundStyle(.secondary)

            Spacer()
        }
        .padding(Theme.spacing)
        .ancreBackground()
        .sheet(isPresented: $isTeacherDashboardPresented) {
            TeacherDashboardView()
        }
        .sheet(isPresented: $isParentRemotePresented) {
            ParentRemoteView()
        }
    }
}

private struct RoleCard: View {
    let title: String
    let subtitle: String
    let symbol: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            GlassCard {
                HStack(spacing: 14) {
                    Image(systemName: symbol)
                        .font(.system(size: 28))
                        .foregroundStyle(Theme.accentGradient)
                    VStack(alignment: .leading, spacing: 4) {
                        Text(title).font(.headline)
                        Text(subtitle)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    Spacer(minLength: 0)
                }
            }
        }
        .buttonStyle(.plain)
    }
}
