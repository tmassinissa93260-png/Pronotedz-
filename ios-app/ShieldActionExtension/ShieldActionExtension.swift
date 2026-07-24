import ManagedSettings
import Foundation

/// Réagit aux boutons de l'écran de blocage. Comme l'écran système ne peut pas
/// afficher de compte à rebours ou de messages qui tournent, le bouton
/// "J'en ai vraiment besoin" ouvre l'app principale (via l'URL scheme, voir
/// AppConstants.urlScheme) sur l'écran d'attente réel (WaitingScreenView).
class ShieldActionExtension: ShieldActionDelegate {
    override func handle(
        action: ShieldAction,
        for application: ApplicationToken,
        completionHandler: @escaping (ShieldActionResponse) -> Void
    ) {
        switch action {
        case .primaryButtonPressed:
            SessionState.recordOverride()
            // .defer garde le shield en place le temps que l'app ouvre
            // et gère elle-même l'attente (30s ou 2min selon SessionState).
            completionHandler(.defer)
            openContainingAppOnWaitingScreen()
        case .secondaryButtonPressed:
            completionHandler(.close)
        @unknown default:
            completionHandler(.close)
        }
    }

    private func openContainingAppOnWaitingScreen() {
        // NOTE non vérifiée : `extensionContext?.open(_:)` n'est pas officiellement
        // documenté comme disponible depuis ShieldActionExtension. À valider dans
        // Xcode — si ça ne fonctionne pas, solution de repli : écrire un flag dans
        // l'App Group ici, et faire lire ce flag par l'app principale via un
        // Darwin notification ou au prochain passage au premier plan.
        guard let url = URL(string: "\(AppConstants.urlScheme)://waiting") else { return }
        extensionContext?.open(url, completionHandler: nil)
    }
}
