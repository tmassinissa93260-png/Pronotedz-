import FamilyControls

/// Demande l'autorisation Écran & Temps d'écran en mode "individuel"
/// (l'utilisateur se restreint lui-même, ce n'est pas un contrôle parental).
@MainActor
final class ScreenTimeAuthorization: ObservableObject {
    @Published var isAuthorized = false

    func requestAuthorization() async {
        do {
            try await AuthorizationCenter.shared.requestAuthorization(for: .individual)
            isAuthorized = AuthorizationCenter.shared.authorizationStatus == .approved
        } catch {
            // À remplacer par une vraie UI d'erreur : l'utilisateur peut refuser
            // ou l'autorisation peut échouer si l'entitlement Family Controls
            // n'est pas encore approuvée par Apple pour ce bundle ID.
            print("Autorisation Screen Time refusée ou échouée : \(error)")
            isAuthorized = false
        }
    }
}
