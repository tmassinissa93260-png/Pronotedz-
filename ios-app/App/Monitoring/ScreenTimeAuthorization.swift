import FamilyControls

/// Demande l'autorisation Écran & Temps d'écran, dans l'un des deux modes
/// que le framework distingue :
/// - `.individual` : l'utilisateur se restreint lui-même. Il peut toujours
///   désinstaller l'app ou révoquer l'autorisation à tout moment — c'est un
///   engagement volontaire, pas un verrou.
/// - `.child` : à utiliser uniquement sur l'appareil d'un enfant déjà
///   rattaché à un adulte via le Partage familial Apple. Une fois accordée,
///   les restrictions ne peuvent plus être levées sans le code Temps d'écran
///   du parent — c'est la vraie différence entre "mode parent" et
///   "mode moi-même", pas un réglage dans notre app.
///
/// Le nom exact des cas (`.individual`/`.child`) est reconstitué de mémoire
/// à partir de la documentation FamilyControls — à vérifier à la compilation,
/// aucun compilateur Swift/iOS disponible dans cet environnement.
@MainActor
final class ScreenTimeAuthorization: ObservableObject {
    @Published var isAuthorized = false

    func requestAuthorization(for role: UserRole) async {
        do {
            switch role {
            case .myself:
                try await AuthorizationCenter.shared.requestAuthorization(for: .individual)
            case .child:
                try await AuthorizationCenter.shared.requestAuthorization(for: .child)
            }
            isAuthorized = AuthorizationCenter.shared.authorizationStatus == .approved
        } catch {
            // À remplacer par une vraie UI d'erreur : l'utilisateur peut refuser,
            // l'autorisation peut échouer si l'entitlement Family Controls n'est
            // pas encore approuvée par Apple pour ce bundle ID, ou — spécifique
            // au mode .child — si cet appareil n'appartient pas à un enfant dans
            // le Partage familial.
            print("Autorisation Screen Time refusée ou échouée : \(error)")
            isAuthorized = false
        }
    }
}
