import SwiftUI

/// Écran installé sur le téléphone du PARENT (pas celui de l'enfant) : entrer
/// le code famille une fois pour voir les demandes de temps en attente et y
/// répondre. Accessible depuis RoleSelectionView via un lien dédié — un
/// parent qui suit son enfant à distance ne configure pas de restrictions
/// sur son propre téléphone.
struct ParentRemoteView: View {
    @State private var familyCode = ""
    @State private var isLinked = false
    @State private var requests: [TimeRequest] = []
    @State private var isLoading = false

    var body: some View {
        if isLinked {
            linkedView
        } else {
            codeEntryView
        }
    }

    private var codeEntryView: some View {
        VStack(spacing: Theme.spacing) {
            Spacer()
            Image(systemName: "antenna.radiowaves.left.and.right")
                .font(.system(size: 44))
                .foregroundStyle(Theme.accentGradient)
            Text("Suivre mon enfant")
                .font(.headline)
            Text("Entre le code affiché dans les réglages parent sur son téléphone.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, Theme.spacing)

            TextField("Code famille", text: $familyCode)
                .textInputAutocapitalization(.characters)
                .multilineTextAlignment(.center)
                .font(.title3)
                .padding()
                .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: Theme.controlCornerRadius))
                .padding(.horizontal, 60)

            Button("Continuer") {
                isLinked = true
            }
            .buttonStyle(PrimaryButtonStyle())
            .padding(.horizontal, 60)
            .disabled(familyCode.trimmingCharacters(in: .whitespaces).isEmpty)

            Spacer()
        }
        .padding(Theme.spacing)
        .ancreBackground()
    }

    private var linkedView: some View {
        VStack(alignment: .leading, spacing: Theme.spacing) {
            Spacer().frame(height: Theme.spacing / 2)

            Text("Demandes en attente")
                .font(.system(.title2, design: .rounded, weight: .bold))

            if isLoading {
                ProgressView().frame(maxWidth: .infinity)
            } else if requests.isEmpty {
                Text("Aucune demande pour l'instant.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            } else {
                ForEach(requests) { request in
                    RequestCard(request: request) { approve in
                        Task { await respond(to: request, approve: approve) }
                    }
                }
            }

            Button("Actualiser") {
                Task { await refresh() }
            }
            .buttonStyle(.bordered)
            .frame(maxWidth: .infinity)

            Spacer()
        }
        .padding(Theme.spacing)
        .ancreBackground()
        .task { await refresh() }
    }

    private func refresh() async {
        isLoading = true
        requests = (try? await TimeRequestSync.fetchRequests(familyCode: familyCode))?
            .filter { $0.status == .pending } ?? []
        isLoading = false
    }

    private func respond(to request: TimeRequest, approve: Bool) async {
        try? await TimeRequestSync.respond(to: request, approve: approve, grantedMinutes: request.requestedMinutes)
        await refresh()
    }
}

private struct RequestCard: View {
    let request: TimeRequest
    let onRespond: (Bool) -> Void

    var body: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 10) {
                Text("Demande de \(request.requestedMinutes) minutes supplémentaires")
                    .font(.headline)
                HStack {
                    Button("Refuser") { onRespond(false) }
                        .buttonStyle(.bordered)
                        .tint(.secondary)
                    Button("Accepter") { onRespond(true) }
                        .buttonStyle(.borderedProminent)
                }
            }
        }
    }
}
