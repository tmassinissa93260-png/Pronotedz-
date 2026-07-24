import SwiftUI

/// Formulaire rempli par le parent lors de la configuration d'un profil
/// enfant : à qui envoyer le "témoin" en cas de craquage, et un code à 4
/// chiffres pour protéger l'accès aux réglages parent dans l'app (voir
/// ParentSettings.swift pour ce que ce code protège vraiment — pas grand-chose
/// de plus qu'un tap accidentel, la vraie protection vient d'ailleurs).
struct ParentSetupView: View {
    let onCompleted: () -> Void

    @State private var parentName = ""
    @State private var phoneNumber = ""
    @State private var pin = ""

    private var isValid: Bool {
        !parentName.trimmingCharacters(in: .whitespaces).isEmpty
            && phoneNumber.count >= 6
            && pin.count == 4
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.spacing) {
            Spacer().frame(height: Theme.spacing / 2)

            Text("Réglages parent")
                .font(.system(.title2, design: .rounded, weight: .bold))

            Text("Ces informations restent sur l'appareil, rien n'est envoyé à un serveur.")
                .font(.subheadline)
                .foregroundStyle(.secondary)

            GlassCard {
                VStack(alignment: .leading, spacing: 12) {
                    TextField("Ton nom (affiché à l'enfant)", text: $parentName)
                        .textFieldStyle(.plain)
                    Divider()
                    TextField("Ton numéro (pour le \"témoin\")", text: $phoneNumber)
                        .textFieldStyle(.plain)
                        .keyboardType(.phonePad)
                    Divider()
                    SecureField("Code à 4 chiffres pour les réglages", text: $pin)
                        .textFieldStyle(.plain)
                        .keyboardType(.numberPad)
                }
            }

            Spacer()

            Button("Terminer la configuration") {
                var settings = ParentSettings.load()
                settings.parentName = parentName
                settings.parentPhoneNumber = phoneNumber
                settings.setPIN(pin)
                settings.save()
                onCompleted()
            }
            .buttonStyle(PrimaryButtonStyle())
            .disabled(!isValid)
            .opacity(isValid ? 1 : 0.5)
        }
        .padding(Theme.spacing)
        .ancreBackground()
    }
}
