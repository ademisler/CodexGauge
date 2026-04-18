import SwiftUI

struct AccountRowView: View {
    let account: StoredAccount
    let state: AccountRuntimeState
    let isActive: Bool
    let canSwitch: Bool
    let isSelected: Bool
    let isReauthenticating: Bool
    let onSelect: () -> Void
    let onSaveNickname: (String) -> Void
    let onRefresh: () -> Void
    let onSwitch: () -> Void
    let onReauthenticate: () -> Void
    let onOpenFolder: () -> Void
    let onRemove: () -> Void

    @State private var draftNickname = ""

    var body: some View {
        VStack(alignment: .leading, spacing: self.isSelected ? 10 : 7) {
            self.headerRow
            self.summaryContent

            if self.isSelected {
                Divider()
                    .overlay(Color.primary.opacity(0.08))

                if let snapshot = self.state.snapshot, snapshot.hasQuotaWindows {
                    VStack(spacing: 8) {
                        if let primaryWindow = snapshot.primaryWindow {
                            CompactQuotaLine(title: primaryWindow.shortLabel, window: primaryWindow, tint: self.tint(for: primaryWindow))
                        }
                        if let secondaryWindow = snapshot.secondaryWindow {
                            CompactQuotaLine(title: secondaryWindow.shortLabel, window: secondaryWindow, tint: self.tint(for: secondaryWindow))
                        }
                    }
                }

                HStack(spacing: 6) {
                    RowActionButton(systemName: "arrow.clockwise", action: self.onRefresh)
                        .help("Refresh")
                    if self.canSwitch {
                        RowActionButton(systemName: "arrow.left.arrow.right.circle", action: self.onSwitch)
                            .help("Switch active account")
                    }
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
        .padding(.vertical, self.isSelected ? 11 : 9)
        .background(
            RoundedRectangle(cornerRadius: 15, style: .continuous)
                .fill(self.isSelected ? Color.accentColor.opacity(0.08) : Color(NSColor.controlBackgroundColor)))
        .overlay(
            RoundedRectangle(cornerRadius: 15, style: .continuous)
                .stroke(self.isSelected ? Color.accentColor.opacity(0.28) : Color.primary.opacity(0.11), lineWidth: self.isSelected ? 1.2 : 1))
        .shadow(color: Color.black.opacity(self.isSelected ? 0.08 : 0.04), radius: self.isSelected ? 8 : 4, y: 1)
        .contentShape(RoundedRectangle(cornerRadius: 15, style: .continuous))
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

    private var headerRow: some View {
        HStack(alignment: .top, spacing: 10) {
            VStack(alignment: .leading, spacing: 3) {
                Text(self.account.displayName)
                    .font(.system(size: 13, weight: .semibold))
                    .lineLimit(1)
                Text(self.secondaryLine)
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }

            Spacer(minLength: 8)

            HStack(spacing: 6) {
                if self.isActive {
                    Text("Active")
                        .font(.system(size: 10, weight: .semibold, design: .rounded))
                        .padding(.horizontal, 7)
                        .padding(.vertical, 4)
                        .background(
                            Capsule(style: .continuous)
                                .fill(Color.accentColor.opacity(0.12)))
                }

                if self.canSwitch && !self.isSelected {
                    HeaderActionPill(
                        title: "Switch",
                        systemName: "arrow.left.arrow.right",
                        action: self.onSwitch)
                        .help("Switch active account")
                }

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
                        .frame(width: 24, height: 24)
                } else {
                    StatusBadge(snapshot: self.state.snapshot, hasError: self.state.errorMessage != nil)
                }
            }
        }
    }

    @ViewBuilder
    private var summaryContent: some View {
        if let snapshot = self.state.snapshot {
            if snapshot.hasQuotaWindows {
                HStack(alignment: .top, spacing: 7) {
                    if let primaryWindow = snapshot.primaryWindow {
                        CompactQuotaPill(
                            title: primaryWindow.shortLabel,
                            window: primaryWindow,
                            tint: self.tint(for: primaryWindow))
                    }
                    if let secondaryWindow = snapshot.secondaryWindow {
                        CompactQuotaPill(
                            title: secondaryWindow.shortLabel,
                            window: secondaryWindow,
                            tint: self.tint(for: secondaryWindow))
                    }
                }
            } else if snapshot.isQuotaBlocked {
                InlineStatePill(
                    text: "Quota reached",
                    systemName: "exclamationmark.circle.fill",
                    tint: .red)
            } else {
                InlineStatePill(
                    text: "No quota data",
                    systemName: "chart.bar.xaxis",
                    tint: .secondary)
            }
        } else if let errorMessage = self.state.errorMessage {
            InlineStatePill(
                text: errorMessage,
                systemName: "exclamationmark.triangle.fill",
                tint: .orange,
                lineLimit: self.isSelected ? 4 : 2)
        } else {
            InlineStatePill(
                text: "Waiting for data",
                systemName: "clock",
                tint: .secondary)
        }
    }

    private var secondaryLine: String {
        self.account.emailHint ?? self.account.source.displayName
    }

    private func tint(for window: UsageWindowSnapshot) -> Color {
        let remaining = window.remainingPercent
        if remaining <= 10 {
            return .red
        }
        if remaining <= 20 {
            return .orange
        }
        return .green
    }
}

private struct CompactQuotaPill: View {
    let title: String
    let window: UsageWindowSnapshot
    let tint: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack(spacing: 6) {
                Text(self.title.uppercased())
                    .font(.system(size: 10, weight: .bold, design: .rounded))
                    .foregroundStyle(self.tint)

                Spacer(minLength: 4)

                Text("\(Int(self.window.remainingPercent.rounded()))%")
                    .font(.system(size: 11, weight: .semibold, design: .rounded))
                    .foregroundStyle(.primary)
            }

            ProgressView(value: self.window.remainingPercent, total: 100)
                .tint(self.tint)
                .scaleEffect(y: 0.42)

            if let resetAt = self.window.compactResetAtDisplay {
                HStack(spacing: 4) {
                    Image(systemName: "clock")
                        .font(.system(size: 9, weight: .semibold))
                    Text(resetAt)
                        .lineLimit(1)
                }
                .font(.system(size: 10))
                .foregroundStyle(.secondary)
            }
        }
        .padding(.horizontal, 9)
        .padding(.vertical, 7)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .fill(self.tint.opacity(0.08)))
        .overlay(
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .stroke(self.tint.opacity(0.16), lineWidth: 1))
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

private struct InlineStatePill: View {
    let text: String
    let systemName: String
    let tint: Color
    var lineLimit = 1

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: self.systemName)
                .font(.system(size: 10, weight: .semibold))
            Text(self.text)
                .lineLimit(self.lineLimit)
                .multilineTextAlignment(.leading)
        }
        .font(.system(size: 11, weight: .medium))
        .foregroundStyle(self.tint)
        .padding(.horizontal, 9)
        .padding(.vertical, 7)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .fill(self.tint.opacity(0.08)))
        .overlay(
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .stroke(self.tint.opacity(0.14), lineWidth: 1))
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
                Text("\(Int(snapshot.lowestRemainingPercent.rounded()))%")
                    .font(.system(size: 10, weight: .semibold, design: .rounded))
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.horizontal, 7)
        .padding(.vertical, 4)
        .background(
            Capsule(style: .continuous)
                .fill(Color(NSColor.windowBackgroundColor)))
    }

    private var tint: Color {
        if self.hasError {
            return .orange
        }

        guard let snapshot else {
            return .secondary
        }

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

private struct HeaderActionPill: View {
    let title: String
    let systemName: String
    let action: () -> Void

    var body: some View {
        Button(action: self.action) {
            HStack(spacing: 5) {
                Image(systemName: self.systemName)
                    .font(.system(size: 9, weight: .semibold))
                Text(self.title)
                    .font(.system(size: 10, weight: .semibold, design: .rounded))
            }
            .padding(.horizontal, 7)
            .padding(.vertical, 4)
            .background(
                Capsule(style: .continuous)
                    .fill(Color(NSColor.windowBackgroundColor)))
        }
        .buttonStyle(.plain)
    }
}
