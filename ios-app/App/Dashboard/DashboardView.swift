import SwiftUI

/// État de repos de l'app, affiché quand aucune session/attente n'est en
/// cours. Donne un point d'entrée clair au coach IA et à la modification
/// des apps surveillées, plutôt que de laisser l'app "sans écran" entre
/// deux événements DeviceActivity.
struct DashboardView: View {
    let onEditApps: () -> Void

    @State private var isCoachPresented = false
    @State private var isParentSettingsPresented = false

    private var role: UserRole { UserRole.load() ?? .myself }
    private var isCoachAvailable: Bool {
        role == .myself || ParentSettings.load().isCoachEnabledForChild
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.spacing) {
                Spacer().frame(height: Theme.spacing / 2)

                Text("Ancre")
                    .font(.system(.largeTitle, design: .rounded, weight: .bold))
                    .foregroundStyle(Theme.accentGradient)

                GlassCard {
                    VStack(alignment: .leading, spacing: 8) {
                        Label("Statistiques du jour", systemImage: "chart.bar.fill")
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(.secondary)
                        Text("\(SessionState.overridesToday) réouverture(s) forcée(s) aujourd'hui")
                            .font(.title3.weight(.medium))
                        Text("Le détail par app vit dans l'extension DeviceActivityReport (process séparé, cf. README-SETUP.md).")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }

                if isCoachAvailable {
                    Button {
                        isCoachPresented = true
                    } label: {
                        GlassCard {
                            HStack(spacing: 14) {
                                Image(systemName: "sparkles")
                                    .font(.system(size: 28))
                                    .foregroundStyle(Theme.accentGradient)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text("Parler au coach").font(.headline)
                                    Text("Sur l'appareil, privé, disponible à tout moment.")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                                Spacer()
                                Image(systemName: "chevron.right")
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }
                    .buttonStyle(.plain)
                } else if role == .child {
                    GlassCard {
                        Label("Coach IA désactivé par le parent", systemImage: "sparkles")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                }

                Button("Modifier les apps surveillées", action: onEditApps)
                    .buttonStyle(.bordered)
                    .frame(maxWidth: .infinity)

                if role == .child {
                    Button("Réglages parent") {
                        isParentSettingsPresented = true
                    }
                    .buttonStyle(.bordered)
                    .tint(.secondary)
                    .frame(maxWidth: .infinity)
                }

                Spacer()
            }
            .padding(Theme.spacing)
        }
        .ancreBackground()
        .sheet(isPresented: $isCoachPresented) {
            CoachEntryView(
                interestProfile: InterestProfile.load(),
                overridesToday: SessionState.overridesToday
            )
        }
        .sheet(isPresented: $isParentSettingsPresented) {
            ParentSettingsGateView()
        }
    }
}
