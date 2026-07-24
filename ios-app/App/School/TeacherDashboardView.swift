import SwiftUI

/// Accès enseignant, volontairement séparé du flux élève/parent — un prof
/// ne restreint pas son propre téléphone, il consulte seulement les chiffres
/// de sa classe. Accessible directement depuis RoleSelectionView.
struct TeacherDashboardView: View {
    @State private var classCode = ""
    @State private var checkIns: [StudentCheckIn] = []
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.spacing) {
            Spacer().frame(height: Theme.spacing / 2)

            Text("Ma classe")
                .font(.system(.title2, design: .rounded, weight: .bold))

            HStack {
                TextField("Code de classe", text: $classCode)
                    .textFieldStyle(.plain)
                    .textInputAutocapitalization(.characters)
                    .padding(12)
                    .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: Theme.controlCornerRadius))

                Button("Charger") {
                    Task { await load() }
                }
                .buttonStyle(.borderedProminent)
                .disabled(classCode.isEmpty || isLoading)
            }

            if isLoading {
                ProgressView().frame(maxWidth: .infinity)
            } else if let errorMessage {
                Text(errorMessage).font(.caption).foregroundStyle(.red)
            } else if checkIns.isEmpty {
                Text("Aucune donnée pour ce code aujourd'hui.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            } else {
                ScrollView {
                    VStack(spacing: 12) {
                        ForEach(checkIns.sorted(by: { $0.overridesToday > $1.overridesToday })) { checkIn in
                            GlassCard {
                                HStack {
                                    Text(checkIn.studentName).font(.headline)
                                    Spacer()
                                    Text("\(checkIn.overridesToday) réouverture(s)")
                                        .font(.subheadline)
                                        .foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                }
            }

            Spacer()
        }
        .padding(Theme.spacing)
        .ancreBackground()
    }

    private func load() async {
        isLoading = true
        errorMessage = nil
        do {
            checkIns = try await SchoolSync.fetchClassCheckIns(classCode: classCode)
        } catch {
            errorMessage = "Impossible de charger la classe (\(error.localizedDescription))."
        }
        isLoading = false
    }
}
