import SwiftUI
import FamilyControls
import ManagedSettings

/// Écran où l'utilisateur choisit les apps à surveiller (ex. TikTok, Instagram).
/// Apple ne donne jamais le nom/bundle ID réel de l'app choisie à ton code —
/// seulement des tokens opaques, affichables uniquement via les vues fournies
/// par FamilyControls (ex. `Label(token)`). C'est voulu par Apple pour la vie privée.
struct AppSelectionPicker: View {
    let onCompleted: () -> Void

    @State private var selection = FamilyActivitySelection()
    @State private var isPickerPresented = false

    static var hasSavedSelection: Bool {
        UserDefaults.shared.data(forKey: "monitoredSelection") != nil
    }

    var body: some View {
        VStack(spacing: Theme.spacing) {
            Spacer()

            Image(systemName: "shield.lefthalf.filled")
                .font(.system(size: 56))
                .foregroundStyle(Theme.accentGradient)

            Text("Choisis les apps à encadrer")
                .font(.system(.title2, design: .rounded, weight: .bold))

            Text("TikTok, Instagram, ce que tu veux — tu peux en changer plus tard.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)

            GlassCard {
                HStack {
                    Image(systemName: "apps.iphone")
                        .foregroundStyle(Theme.accentGradient)
                    Text(selectionSummary)
                        .font(.subheadline.weight(.medium))
                    Spacer()
                }
            }

            Button("Ouvrir le sélecteur") {
                isPickerPresented = true
            }
            .buttonStyle(.bordered)
            .familyActivityPicker(isPresented: $isPickerPresented, selection: $selection)

            Spacer()

            Button("Valider") {
                saveSelectionAndApplyShield()
            }
            .buttonStyle(PrimaryButtonStyle())
            .disabled(selection.applicationTokens.isEmpty && selection.categoryTokens.isEmpty)
        }
        .padding(Theme.spacing)
        .ancreBackground()
    }

    private var selectionSummary: String {
        let count = selection.applicationTokens.count + selection.categoryTokens.count
        return count == 0 ? "Aucune app choisie pour l'instant" : "\(count) app(s)/catégorie(s) choisies"
    }

    private func saveSelectionAndApplyShield() {
        // Le token est encodé et stocké dans l'App Group pour que
        // DeviceActivityMonitorExtension puisse l'utiliser au moment
        // d'appliquer le shield, sans jamais connaître l'identité réelle de l'app.
        if let encoded = try? JSONEncoder().encode(selection) {
            UserDefaults.shared.set(encoded, forKey: "monitoredSelection")
        }
        FrictionScheduler.startMonitoring(selection: selection)
        onCompleted()
    }
}
