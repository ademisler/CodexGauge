import SwiftUI

struct AccountRowView: View {
    let account: StoredAccount
    let state: AccountRuntimeState
    let isSelected: Bool
    let isReauthenticating: Bool
    let onSelect: () -> Void
    let onSaveNickname: (String) -> Void
    let onRefresh: () -> Void
    let onReauthenticate: () -> Void
    let onOpenFolder: () -> Void
    let onRemove: () -> Void

    @State private var draftNickname = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .top, spacing: 8) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(self.account.displayName)
                        .font(.system(size: 13, weight: .semibold))
                        .lineLimit(1)
                    Text(self.secondaryLine)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }

                Spacer()

                if let snapshot = self.state.snapshot {
                    Text(snapshot.planDisplayName)
                        .font(.system(size: 10, weight: .semibold, design: .rounded))
                        .padding(.horizontal, 7)
                        .padding(.vertical, 4)
                        .background(
                            Capsule(style: .continuous)
                                .fill(Color(NSColor.windowBackgroundColor)))
                }

                if self.state.isLoading || self.isReauthenticating {
                    ProgressView()
                        .controlSize(.small)
                } else {
                    StatusBadge(snapshot: self.state.snapshot, hasError: self.state.errorMessage != nil)
                }
            }

            if let snapshot = self.state.snapshot {
                if snapshot.hasQuotaWindows {
                    if let primaryWindow = snapshot.primaryWindow {
                        CompactQuotaLine(title: primaryWindow.shortLabel, window: primaryWindow, tint: .blue)
                    }
                    if let secondaryWindow = snapshot.secondaryWindow {
                        CompactQuotaLine(title: secondaryWindow.shortLabel, window: secondaryWindow, tint: self.tint(for: snapshot))
                    }
                } else if snapshot.isQuotaBlocked {
                    Text("Quota reached")
                        .font(.caption2.weight(.semibold))
                        .foregroundStyle(.red)
                } else {
                    Text("No quota data")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            } else if let errorMessage = self.state.errorMessage {
                Text(errorMessage)
                    .font(.caption2)
                    .foregroundStyle(.orange)
                    .lineLimit(self.isSelected ? 4 : 2)
            } else {
                Text("Waiting for data")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }

            if self.isSelected {
                Divider()
                    .overlay(Color.primary.opacity(0.06))

                HStack(spacing: 6) {
                    RowActionButton(systemName: "arrow.clockwise", action: self.onRefresh)
                        .help("Refresh")
                    RowActionButton(systemName: "person.crop.circle.badge.checkmark", action: self.onReauthenticate)
                        .help("Reauthenticate")
                    RowActionButton(systemName: "folder", action: self.onOpenFolder)
                        .help("Open folder")
                    RowActionButton(systemName: "trash", role: .destructive, action: self.onRemove)
                        .help("Remove")

                    Spacer()

                    if let updatedAt = self.state.snapshot?.updatedAt {
                        Text(updatedAt.formatted(date: .omitted, time: .shortened))
                            .font(.caption2.monospacedDigit())
                            .foregroundStyle(.secondary)
                    }
                }

                HStack(spacing: 8) {
                    TextField("Label", text: self.$draftNickname)
                        .textFieldStyle(.plain)
                        .font(.caption)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 6)
                        .background(
                            RoundedRectangle(cornerRadius: 8, style: .continuous)
                                .fill(Color(NSColor.windowBackgroundColor)))
                        .onSubmit {
                            self.onSaveNickname(self.draftNickname)
                        }

                    Button("Save") {
                        self.onSaveNickname(self.draftNickname)
                    }
                    .buttonStyle(.plain)
                    .font(.caption.weight(.semibold))
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(
                        Capsule(style: .continuous)
                            .fill(Color.accentColor.opacity(0.12)))
                }
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .background(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .fill(self.isSelected ? Color.accentColor.opacity(0.08) : Color(NSColor.controlBackgroundColor)))
        .overlay(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .stroke(self.isSelected ? Color.accentColor.opacity(0.22) : Color.primary.opacity(0.05), lineWidth: 1))
        .contentShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        .onTapGesture {
            self.onSelect()
        }
        .onAppear {
            self.draftNickname = self.account.nickname ?? ""
        }
        .onChange(of: self.account.id) {
            self.draftNickname = self.account.nickname ?? ""
        }
    }

    private var secondaryLine: String {
        self.account.emailHint ?? self.account.source.displayName
    }

    private func tint(for snapshot: AccountUsageSnapshot) -> Color {
        let remaining = snapshot.lowestRemainingPercent
        if remaining <= 10 {
            return .red
        }
        if remaining <= 20 {
            return .orange
        }
        return .green
    }
}

private struct CompactQuotaLine: View {
    let title: String
    let window: UsageWindowSnapshot?
    let tint: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack(spacing: 8) {
                Text(self.title)
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(.secondary)
                Spacer()
                if let window {
                    Text("\(Int(window.remainingPercent.rounded()))%")
                        .font(.caption2.monospacedDigit())
                        .foregroundStyle(.secondary)
                } else {
                    Text("None")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }

            ProgressView(value: self.window?.remainingPercent ?? 0, total: 100)
                .tint(self.tint)
                .scaleEffect(y: 0.55)

            if let resetAt = self.window?.resetAtDisplay {
                HStack(spacing: 4) {
                    Image(systemName: "clock")
                        .font(.system(size: 9, weight: .semibold))
                    Text(resetAt)
                        .font(.caption2.monospacedDigit())
                }
                .foregroundStyle(.secondary)
            }
        }
    }
}

private struct StatusBadge: View {
    let snapshot: AccountUsageSnapshot?
    let hasError: Bool

    var body: some View {
        HStack(spacing: 5) {
            Circle()
                .fill(self.tint)
                .frame(width: 7, height: 7)

            if let snapshot {
                Text("\(Int(snapshot.lowestRemainingPercent.rounded()))")
                    .font(.caption2.monospacedDigit())
                    .foregroundStyle(.secondary)
            }
        }
    }

    private var tint: Color {
        if self.hasError {
            return .orange
        }

        let remaining = self.snapshot?.lowestRemainingPercent ?? 101
        if remaining <= 10 {
            return .red
        }
        if remaining <= 20 {
            return .orange
        }
        return .green
    }
}

private struct RowActionButton: View {
    let systemName: String
    var role: ButtonRole?
    let action: () -> Void

    var body: some View {
        Button(role: self.role, action: self.action) {
            Image(systemName: self.systemName)
                .font(.system(size: 12, weight: .semibold))
                .frame(width: 24, height: 24)
                .background(
                    RoundedRectangle(cornerRadius: 7, style: .continuous)
                        .fill(Color(NSColor.windowBackgroundColor)))
        }
        .buttonStyle(.plain)
    }
}
