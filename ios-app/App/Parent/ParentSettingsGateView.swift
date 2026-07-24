import SwiftUI

/// Protège l'accès aux réglages parent (activer le coach pour l'enfant,
/// changer le contact du témoin) par le code à 4 chiffres défini pendant
/// ParentSetupView. Rappel : ce PIN est une friction applicative, pas une
/// sécurité réelle (voir ParentSettings.swift) — un enfant qui réinstalle
/// l'app repart de zéro. Suffisant pour éviter un tap accidentel, pas pour
/// un enfant déterminé à contourner activement.
struct ParentSettingsGateView: View {
    @State private var enteredPIN = ""
    @State private var isUnlocked = false
    @State private var showError = false

    var body: some View {
        if isUnlocked {
            ParentSettingsView()
        } else {
            VStack(spacing: Theme.spacing) {
                Spacer()
                Image(systemName: "lock.shield")
                    .font(.system(size: 44))
                    .foregroundStyle(Theme.accentGradient)
                Text("Code parent")
                    .font(.headline)

                SecureField("••••", text: $enteredPIN)
                    .keyboardType(.numberPad)
                    .multilineTextAlignment(.center)
                    .font(.title2)
                    .frame(width: 120)
                    .padding()
                    .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: Theme.controlCornerRadius))

                if showError {
                    Text("Code incorrect").font(.caption).foregroundStyle(.red)
                }

                Button("Valider") {
                    if ParentSettings.load().verifyPIN(enteredPIN) {
                        isUnlocked = true
                    } else {
                        showError = true
                    }
                }
                .buttonStyle(PrimaryButtonStyle())
                .padding(.horizontal, 60)

                Spacer()
            }
            .padding(Theme.spacing)
            .ancreBackground()
        }
    }
}

private struct ParentSettingsView: View {
    @State private var settings = ParentSettings.load()

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.spacing) {
            Spacer().frame(height: Theme.spacing / 2)
            Text("Réglages parent")
                .font(.system(.title2, design: .rounded, weight: .bold))

            GlassCard {
                Toggle("Autoriser le coach IA pour l'enfant", isOn: Binding(
                    get: { settings.isCoachEnabledForChild },
                    set: { settings.isCoachEnabledForChild = $0; settings.save() }
                ))
                Text("Les échanges tournent sur l'appareil, mais aucun filtrage de sécurité spécifique aux mineurs n'a été ajouté au-delà des instructions données au modèle — à évaluer avant d'activer réellement pour un enfant.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            GlassCard {
                VStack(alignment: .leading, spacing: 10) {
                    Text("Limite quotidienne : \(settings.dailyLimitMinutes) min")
                        .font(.subheadline.weight(.medium))
                    Stepper(
                        "",
                        value: Binding(
                            get: { settings.dailyLimitMinutes },
                            set: {
                                settings.dailyLimitMinutes = $0
                                settings.save()
                                FrictionScheduler.reregisterIfPossible()
                            }
                        ),
                        in: 15...480,
                        step: 15
                    )
                    .labelsHidden()
                }
            }

            GlassCard {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Code famille").font(.subheadline.weight(.medium))
                    Text(settings.familyCode)
                        .font(.system(.title2, design: .monospaced, weight: .bold))
                        .foregroundStyle(Theme.accentGradient)
                    Text("À entrer sur ton propre téléphone, dans « Je veux suivre mon enfant à distance », pour recevoir ses demandes de temps en plus.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            Spacer()
        }
        .padding(Theme.spacing)
        .ancreBackground()
    }
}
