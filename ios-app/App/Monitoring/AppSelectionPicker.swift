import SwiftUI
import FamilyControls
import ManagedSettings

/// Écran où l'utilisateur choisit les apps à surveiller (ex. TikTok, Instagram).
/// Apple ne donne jamais le nom/bundle ID réel de l'app choisie à ton code —
/// seulement des tokens opaques, affichables uniquement via les vues fournies
/// par FamilyControls (ex. `Label(token)`). C'est voulu par Apple pour la vie privée.
struct AppSelectionPicker: View {
    @State private var selection = FamilyActivitySelection()
    @State private var isPickerPresented = false

    var body: some View {
        VStack(spacing: 16) {
            Text("Choisis les apps à encadrer")
                .font(.headline)

            Button("Ouvrir le sélecteur") {
                isPickerPresented = true
            }
            .familyActivityPicker(isPresented: $isPickerPresented, selection: $selection)

            Button("Valider") {
                saveSelectionAndApplyShield()
            }
            .disabled(selection.applicationTokens.isEmpty && selection.categoryTokens.isEmpty)
        }
        .padding()
    }

    private func saveSelectionAndApplyShield() {
        // Le token est encodé et stocké dans l'App Group pour que
        // DeviceActivityMonitorExtension puisse l'utiliser au moment
        // d'appliquer le shield, sans jamais connaître l'identité réelle de l'app.
        if let encoded = try? JSONEncoder().encode(selection) {
            UserDefaults.shared.set(encoded, forKey: "monitoredSelection")
        }
        FrictionScheduler.startMonitoring(selection: selection)
    }
}
