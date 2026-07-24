import ManagedSettings
import ManagedSettingsUI
import UIKit

/// Personnalise l'écran système affiché quand une app surveillée est bloquée.
/// Template figé côté Apple (titre/sous-titre/icône/couleur/2 boutons) — pas de
/// compte à rebours dynamique possible ici, voir docs/concept-produit.md section 6bis.
class ShieldConfigurationDataSource: ShieldConfigurationDataSource {
    override func configuration(shielding application: Application) -> ShieldConfiguration {
        ShieldConfiguration(
            backgroundBlurStyle: .systemMaterialDark,
            icon: UIImage(systemName: "shield.lefthalf.filled")?
                .withTintColor(.systemIndigo, renderingMode: .alwaysOriginal),
            title: ShieldConfiguration.Label(
                text: "Pas tout de suite",
                color: .white
            ),
            subtitle: ShieldConfiguration.Label(
                text: "Chaque scroll est une petite décharge de dopamine imprévisible — "
                    + "c'est ce qui te fait revenir, pas le contenu lui-même.",
                color: .white
            ),
            primaryButtonLabel: ShieldConfiguration.Label(
                text: "J'en ai vraiment besoin",
                color: .white
            ),
            primaryButtonBackgroundColor: .systemIndigo,
            secondaryButtonLabel: ShieldConfiguration.Label(
                text: "Plus tard",
                color: .white
            )
        )
    }
}
