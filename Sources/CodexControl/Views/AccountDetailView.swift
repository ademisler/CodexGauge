import SwiftUI

struct AccountDetailView: View {
    let account: StoredAccount
    let state: AccountRuntimeState
    let isReauthenticating: Bool
    let onSaveNickname: (String) -> Void
    let onRefresh: () -> Void
    let onReauthenticate: () -> Void
    let onOpenFolder: () -> Void
    let onRemove: () -> Void

    @State private var draftNickname = ""

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                self.headerCard
                self.statsGrid

                if let errorMessage = self.state.errorMessage {
                    DetailCard {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Last Error")
                                .font(.headline)
                            Text(errorMessage)
                                .font(.body)
                                .foregroundStyle(.secondary)
                                .textSelection(.enabled)
                        }
                    }
                }

                DetailCard {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Account Details")
                            .font(.headline)

                        InfoRow(title: "Source", value: self.account.source.displayName)
                        InfoRow(title: "Email", value: self.state.snapshot?.email ?? self.account.emailHint ?? "Unknown")
                        InfoRow(title: "Provider ID", value: self.state.snapshot?.providerAccountID ?? self.account.providerAccountID ?? "Unknown")
                        InfoRow(title: "CODEX_HOME", value: self.account.codexHomePath)
                    }
                }
            }
            .padding(16)
        }
        .onAppear {
            self.draftNickname = self.account.nickname ?? ""
        }
        .onChange(of: self.account.id) {
            self.draftNickname = self.account.nickname ?? ""
        }
        .background(Color(NSColor.textBackgroundColor))
    }

    private var headerCard: some View {
        DetailCard {
            VStack(alignment: .leading, spacing: 14) {
                HStack(alignment: .top, spacing: 12) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(self.account.displayName)
                            .font(.title2.weight(.semibold))
                        Text(self.state.snapshot?.planDisplayName ?? "Plan details pending")
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    if self.state.isLoading || self.isReauthenticating {
                        ProgressView()
                    }
                }

                HStack(spacing: 8) {
                    TextField("Label", text: self.$draftNickname)
                        .textFieldStyle(.roundedBorder)
                    Button("Save") {
                        self.onSaveNickname(self.draftNickname)
                    }
                }

                HStack(spacing: 8) {
                    Button("Refresh", action: self.onRefresh)
                        .buttonStyle(.borderedProminent)
                    Button("Reauthenticate", action: self.onReauthenticate)
                        .buttonStyle(.bordered)
                    Button("Open Folder", action: self.onOpenFolder)
                        .buttonStyle(.bordered)
                    Button("Remove", role: .destructive, action: self.onRemove)
                        .buttonStyle(.bordered)
                }

                if let updatedAt = self.state.snapshot?.updatedAt {
                    Text("Last updated: \(updatedAt.formatted(date: .abbreviated, time: .shortened))")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
        }
    }

    private var statsGrid: some View {
        LazyVGrid(
            columns: [
                GridItem(.flexible(minimum: 220), spacing: 12),
                GridItem(.flexible(minimum: 220), spacing: 12),
                GridItem(.flexible(minimum: 220), spacing: 12),
            ],
            spacing: 12)
        {
            QuotaCard(
                title: self.state.snapshot?.primaryWindow?.displayName ?? "Primary Quota",
                accent: self.accent(for: self.state.snapshot?.primaryWindow),
                window: self.state.snapshot?.primaryWindow)
            QuotaCard(
                title: self.state.snapshot?.secondaryWindow?.displayName ?? "Secondary Quota",
                accent: self.accent(for: self.state.snapshot?.secondaryWindow),
                window: self.state.snapshot?.secondaryWindow)
            CreditsCard(snapshot: self.state.snapshot?.credits)
        }
    }

    private func accent(for window: UsageWindowSnapshot?) -> Color {
        let remaining = window?.remainingPercent ?? 101
        if remaining <= 10 {
            return .red
        }
        if remaining <= 20 {
            return .orange
        }
        return .green
    }
}

private struct DetailCard<Content: View>: View {
    @ViewBuilder let content: Content

    var body: some View {
        self.content
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(
                RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .fill(Color(NSColor.controlBackgroundColor)))
            .overlay(
                RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .stroke(Color.primary.opacity(0.06), lineWidth: 1))
    }
}

private struct QuotaCard: View {
    let title: String
    let accent: Color
    let window: UsageWindowSnapshot?

    var body: some View {
        DetailCard {
            VStack(alignment: .leading, spacing: 12) {
                Text(self.title)
                    .font(.headline)

                if let window {
                    Text("\(Int(window.remainingPercent.rounded()))%")
                        .font(.system(size: 34, weight: .bold, design: .rounded))
                        .foregroundStyle(self.accent)
                    ProgressView(value: window.remainingPercent, total: 100)
                        .tint(self.accent)
                    if let resetAt = window.resetAtDisplay {
                        Text("Resets: \(resetAt)")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                } else {
                    Text("No data")
                        .font(.title3.weight(.semibold))
                        .foregroundStyle(.secondary)
                }
            }
        }
    }
}

private struct CreditsCard: View {
    let snapshot: CreditsBalanceSnapshot?

    var body: some View {
        DetailCard {
            VStack(alignment: .leading, spacing: 12) {
                Text("Credits")
                    .font(.headline)

                if let snapshot {
                    Text(snapshot.displayValue)
                        .font(.system(size: 34, weight: .bold, design: .rounded))
                        .foregroundStyle(Color.accentColor)
                    if snapshot.unlimited {
                        Text("This account appears to have unlimited credits.")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    } else if snapshot.hasCredits {
                        Text("Credit balance available.")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    } else {
                        Text("No extra credits detected.")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                } else {
                    Text("No data")
                        .font(.title3.weight(.semibold))
                        .foregroundStyle(.secondary)
                }
            }
        }
    }
}

private struct InfoRow: View {
    let title: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(self.title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
            Text(self.value)
                .font(.body)
                .textSelection(.enabled)
        }
    }
}
