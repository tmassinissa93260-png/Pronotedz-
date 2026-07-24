import SwiftUI

/// Rejoindre une classe est optionnel, accessible depuis le tableau de bord
/// — pas une étape obligatoire de l'onboarding, pour ne pas forcer un adulte
/// qui utilise l'app pour lui-même à passer par un flux "école".
struct ClassJoinView: View {
    let onCompleted: () -> Void

    @State private var classCode = ""
    @State private var displayName = ""
    @State private var isSyncing = false

    private var isValid: Bool {
        !classCode.trimmingCharacters(in: .whitespaces).isEmpty
            && !displayName.trimmingCharacters(in: .whitespaces).isEmpty
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.spacing) {
            Spacer().frame(height: Theme.spacing / 2)

            Text("Rejoindre une classe")
                .font(.system(.title2, design: .rounded, weight: .bold))

            Text("Le code vient de ton enseignant(e). Ton prénom sera visible par lui/elle.")
                .font(.subheadline)
                .foregroundStyle(.secondary)

            GlassCard {
                VStack(alignment: .leading, spacing: 12) {
                    TextField("Code de classe", text: $classCode)
                        .textFieldStyle(.plain)
                        .textInputAutocapitalization(.characters)
                    Divider()
                    TextField("Ton prénom", text: $displayName)
                        .textFieldStyle(.plain)
                }
            }

            Spacer()

            Button {
                Task {
                    isSyncing = true
                    let membership = ClassMembership(classCode: classCode, displayName: displayName)
                    membership.save()
                    await SchoolSync.pushDailyCheckIn(membership: membership, overridesToday: SessionState.overridesToday)
                    isSyncing = false
                    onCompleted()
                }
            } label: {
                if isSyncing {
                    ProgressView().tint(.white)
                } else {
                    Text("Rejoindre")
                }
            }
            .buttonStyle(PrimaryButtonStyle())
            .disabled(!isValid || isSyncing)
            .opacity(isValid ? 1 : 0.5)
        }
        .padding(Theme.spacing)
        .ancreBackground()
    }
}
