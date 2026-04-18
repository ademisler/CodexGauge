import Foundation

struct AuthBackedIdentity: Sendable {
    let email: String?
    let authSubject: String?
    let plan: String?
    let providerAccountID: String?
}

struct AuthCredentials: Sendable {
    let accessToken: String
    let refreshToken: String
    let idToken: String?
    let accountId: String?
    let lastRefresh: Date?

    var needsRefresh: Bool {
        guard let lastRefresh else { return true }
        let eightDays: TimeInterval = 8 * 24 * 60 * 60
        return Date().timeIntervalSince(lastRefresh) > eightDays
    }
}

enum CodexAPIError: LocalizedError {
    case authNotFound
    case authInvalid(String)
    case authMissingTokens
    case unauthorized
    case invalidResponse
    case serverError(Int, String?)
    case refreshExpired
    case refreshRevoked
    case refreshReused
    case inconsistentLiveData
    case network(String)

    var errorDescription: String? {
        switch self {
        case .authNotFound:
            return "No `auth.json` was found for this account."
        case let .authInvalid(message):
            return "Failed to read the auth file: \(message)"
        case .authMissingTokens:
            return "The required token fields are missing from `auth.json`."
        case .unauthorized:
            return "The Codex usage API request returned unauthorized."
        case .invalidResponse:
            return "The Codex API response was not in the expected format."
        case let .serverError(code, message):
            if let message, !message.isEmpty {
                return "Codex API error \(code): \(message)"
            }
            return "Codex API error \(code)."
        case .refreshExpired:
            return "The refresh token has expired. Sign in again for this account."
        case .refreshRevoked:
            return "The refresh token was revoked. Sign in again for this account."
        case .refreshReused:
            return "The refresh token can no longer be reused. Sign in again for this account."
        case .inconsistentLiveData:
            return "Live API responses were inconsistent. The data could not be verified."
        case let .network(message):
            return "Network error: \(message)"
        }
    }
}

private struct CodexUsageResponse: Decodable {
    let planType: String?
    let rateLimit: RateLimitDetails?
    let credits: CreditDetails?

    enum CodingKeys: String, CodingKey {
        case planType = "plan_type"
        case rateLimit = "rate_limit"
        case credits
    }
}

private struct RateLimitDetails: Decodable {
    let allowed: Bool?
    let limitReached: Bool?
    let primaryWindow: UsageWindowResponse?
    let secondaryWindow: UsageWindowResponse?

    enum CodingKeys: String, CodingKey {
        case allowed
        case limitReached = "limit_reached"
        case primaryWindow = "primary_window"
        case secondaryWindow = "secondary_window"
    }
}

private struct UsageWindowResponse: Decodable {
    let usedPercent: Double
    let resetAt: Int
    let limitWindowSeconds: Int

    enum CodingKeys: String, CodingKey {
        case usedPercent = "used_percent"
        case resetAt = "reset_at"
        case limitWindowSeconds = "limit_window_seconds"
    }
}

private struct CreditDetails: Decodable {
    let hasCredits: Bool
    let unlimited: Bool
    let balance: Double?

    enum CodingKeys: String, CodingKey {
        case hasCredits = "has_credits"
        case unlimited
        case balance
    }
}

enum CodexAPI {
    private static let refreshEndpoint = URL(string: "https://auth.openai.com/oauth/token")!
    private static let usageDefaultBase = "https://chatgpt.com/backend-api"
    private static let refreshClientID = "app_EMoamEEZ73f0CkXaXp7hrann"
    private static let liveSession: URLSession = {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.requestCachePolicy = .reloadIgnoringLocalCacheData
        configuration.urlCache = nil
        configuration.httpCookieStorage = nil
        return URLSession(configuration: configuration)
    }()

    static func loadIdentity(codexHomePath: String) throws -> AuthBackedIdentity {
        let credentials = try self.loadCredentials(codexHomePath: codexHomePath)
        let payload = credentials.idToken.flatMap(self.parseJWT)
        let auth = payload?["https://api.openai.com/auth"] as? [String: Any]
        let profile = payload?["https://api.openai.com/profile"] as? [String: Any]

        let email = self.normalizeString((payload?["email"] as? String) ?? (profile?["email"] as? String))
        let authSubject = self.normalizeString(payload?["sub"] as? String)
        let plan = self.normalizeString(
            (auth?["chatgpt_plan_type"] as? String) ?? (payload?["chatgpt_plan_type"] as? String))
        let providerAccountID = self.normalizeString(
            credentials.accountId
                ?? (auth?["chatgpt_account_id"] as? String)
                ?? (payload?["chatgpt_account_id"] as? String))

        return AuthBackedIdentity(email: email, authSubject: authSubject, plan: plan, providerAccountID: providerAccountID)
    }

    static func fetchSnapshot(for account: StoredAccount) async throws -> AccountUsageSnapshot {
        var credentials = try self.loadCredentials(codexHomePath: account.codexHomePath)

        if credentials.needsRefresh, !credentials.refreshToken.isEmpty {
            credentials = try await self.refresh(credentials)
            try self.saveCredentials(credentials, codexHomePath: account.codexHomePath)
        }

        do {
            return try await self.fetchVerifiedSnapshot(
                codexHomePath: account.codexHomePath,
                credentials: credentials,
                fallbackEmail: account.emailHint)
        } catch CodexAPIError.unauthorized {
            guard !credentials.refreshToken.isEmpty else {
                throw CodexAPIError.unauthorized
            }
            credentials = try await self.refresh(credentials)
            try self.saveCredentials(credentials, codexHomePath: account.codexHomePath)
            return try await self.fetchVerifiedSnapshot(
                codexHomePath: account.codexHomePath,
                credentials: credentials,
                fallbackEmail: account.emailHint)
        }
    }

    private static func fetchVerifiedSnapshot(
        codexHomePath: String,
        credentials: AuthCredentials,
        fallbackEmail: String?) async throws -> AccountUsageSnapshot
    {
        let first = try await self.fetchSnapshot(
            codexHomePath: codexHomePath,
            credentials: credentials,
            fallbackEmail: fallbackEmail)
        let second = try await self.fetchSnapshot(
            codexHomePath: codexHomePath,
            credentials: credentials,
            fallbackEmail: fallbackEmail)

        if self.isEquivalent(first, second) {
            return second
        }

        let third = try await self.fetchSnapshot(
            codexHomePath: codexHomePath,
            credentials: credentials,
            fallbackEmail: fallbackEmail)

        if self.isEquivalent(first, third) || self.isEquivalent(second, third) {
            return third
        }

        throw CodexAPIError.inconsistentLiveData
    }

    private static func fetchSnapshot(
        codexHomePath: String,
        credentials: AuthCredentials,
        fallbackEmail: String?) async throws -> AccountUsageSnapshot
    {
        let identity = try? self.loadIdentity(codexHomePath: codexHomePath)
        let response = try await self.fetchUsage(
            accessToken: credentials.accessToken,
            accountId: credentials.accountId,
            codexHomePath: codexHomePath)
        let windows = self.makeNormalizedWindows(response.rateLimit)

        return AccountUsageSnapshot(
            email: identity?.email ?? fallbackEmail,
            providerAccountID: identity?.providerAccountID ?? credentials.accountId,
            plan: self.normalizeString(response.planType) ?? identity?.plan,
            allowed: response.rateLimit?.allowed,
            limitReached: response.rateLimit?.limitReached,
            primaryWindow: windows.primary,
            secondaryWindow: windows.secondary,
            credits: response.credits.map(self.makeCredits),
            updatedAt: Date())
    }

    private static func loadCredentials(codexHomePath: String) throws -> AuthCredentials {
        let authURL = URL(fileURLWithPath: codexHomePath, isDirectory: true).appendingPathComponent("auth.json")
        guard FileManager.default.fileExists(atPath: authURL.path) else {
            throw CodexAPIError.authNotFound
        }

        let data = try Data(contentsOf: authURL)
        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw CodexAPIError.authInvalid("invalid JSON")
        }

        if let apiKey = json["OPENAI_API_KEY"] as? String,
           !apiKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        {
            return AuthCredentials(
                accessToken: apiKey,
                refreshToken: "",
                idToken: nil,
                accountId: nil,
                lastRefresh: nil)
        }

        guard let tokens = json["tokens"] as? [String: Any] else {
            throw CodexAPIError.authMissingTokens
        }

        guard let accessToken = self.stringValue(in: tokens, key: "access_token"),
              !accessToken.isEmpty
        else {
            throw CodexAPIError.authMissingTokens
        }

        let refreshToken = self.stringValue(in: tokens, key: "refresh_token") ?? ""
        let idToken = self.stringValue(in: tokens, key: "id_token")
        let accountId = self.stringValue(in: tokens, key: "account_id")

        return AuthCredentials(
            accessToken: accessToken,
            refreshToken: refreshToken,
            idToken: idToken,
            accountId: accountId,
            lastRefresh: self.parseDate(json["last_refresh"]))
    }

    private static func saveCredentials(_ credentials: AuthCredentials, codexHomePath: String) throws {
        let authURL = URL(fileURLWithPath: codexHomePath, isDirectory: true).appendingPathComponent("auth.json")

        var root: [String: Any] = [:]
        if let data = try? Data(contentsOf: authURL),
           let existing = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        {
            root = existing
        }

        var tokens: [String: Any] = [
            "access_token": credentials.accessToken,
            "refresh_token": credentials.refreshToken,
        ]
        if let idToken = credentials.idToken {
            tokens["id_token"] = idToken
        }
        if let accountId = credentials.accountId {
            tokens["account_id"] = accountId
        }

        root["tokens"] = tokens
        root["last_refresh"] = ISO8601DateFormatter().string(from: Date())

        let data = try JSONSerialization.data(withJSONObject: root, options: [.prettyPrinted, .sortedKeys])
        try data.write(to: authURL, options: .atomic)
    }

    private static func refresh(_ credentials: AuthCredentials) async throws -> AuthCredentials {
        var request = URLRequest(url: self.refreshEndpoint)
        request.httpMethod = "POST"
        request.timeoutInterval = 30
        request.cachePolicy = .reloadIgnoringLocalCacheData
        request.httpShouldHandleCookies = false
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("no-cache, no-store, max-age=0", forHTTPHeaderField: "Cache-Control")
        request.setValue("no-cache", forHTTPHeaderField: "Pragma")

        let body: [String: String] = [
            "client_id": self.refreshClientID,
            "grant_type": "refresh_token",
            "refresh_token": credentials.refreshToken,
            "scope": "openid profile email",
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        do {
            let (data, response) = try await self.liveSession.data(for: request)
            guard let http = response as? HTTPURLResponse else {
                throw CodexAPIError.invalidResponse
            }

            if http.statusCode == 401 {
                let code = self.extractErrorCode(from: data)?.lowercased()
                switch code {
                case "refresh_token_reused":
                    throw CodexAPIError.refreshReused
                case "refresh_token_invalidated":
                    throw CodexAPIError.refreshRevoked
                default:
                    throw CodexAPIError.refreshExpired
                }
            }

            guard http.statusCode == 200,
                  let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
            else {
                throw CodexAPIError.invalidResponse
            }

            return AuthCredentials(
                accessToken: (json["access_token"] as? String) ?? credentials.accessToken,
                refreshToken: (json["refresh_token"] as? String) ?? credentials.refreshToken,
                idToken: (json["id_token"] as? String) ?? credentials.idToken,
                accountId: credentials.accountId,
                lastRefresh: Date())
        } catch let error as CodexAPIError {
            throw error
        } catch {
            throw CodexAPIError.network(error.localizedDescription)
        }
    }

    private static func fetchUsage(
        accessToken: String,
        accountId: String?,
        codexHomePath: String) async throws -> CodexUsageResponse
    {
        let url = self.resolveUsageURL(codexHomePath: codexHomePath)
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.timeoutInterval = 30
        request.cachePolicy = .reloadIgnoringLocalCacheData
        request.httpShouldHandleCookies = false
        request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        request.setValue("codex-cli", forHTTPHeaderField: "User-Agent")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue("no-cache, no-store, max-age=0", forHTTPHeaderField: "Cache-Control")
        request.setValue("no-cache", forHTTPHeaderField: "Pragma")

        if let accountId, !accountId.isEmpty {
            request.setValue(accountId, forHTTPHeaderField: "ChatGPT-Account-Id")
        }

        do {
            let (data, response) = try await self.liveSession.data(for: request)
            guard let http = response as? HTTPURLResponse else {
                throw CodexAPIError.invalidResponse
            }

            switch http.statusCode {
            case 200 ... 299:
                return try JSONDecoder().decode(CodexUsageResponse.self, from: data)
            case 401, 403:
                throw CodexAPIError.unauthorized
            default:
                throw CodexAPIError.serverError(http.statusCode, String(data: data, encoding: .utf8))
            }
        } catch let error as CodexAPIError {
            throw error
        } catch {
            throw CodexAPIError.network(error.localizedDescription)
        }
    }

    private static func resolveUsageURL(codexHomePath: String) -> URL {
        let configURL = URL(fileURLWithPath: codexHomePath, isDirectory: true).appendingPathComponent("config.toml")
        let configuredBase: String?
        if let contents = try? String(contentsOf: configURL, encoding: .utf8) {
            configuredBase = self.parseChatGPTBaseURL(from: contents)
        } else {
            configuredBase = nil
        }

        var base = configuredBase?.trimmingCharacters(in: .whitespacesAndNewlines) ?? self.usageDefaultBase
        while base.hasSuffix("/") {
            base.removeLast()
        }
        if base.hasPrefix("https://chatgpt.com"), !base.contains("/backend-api") {
            base += "/backend-api"
        }
        if base.hasPrefix("https://chat.openai.com"), !base.contains("/backend-api") {
            base += "/backend-api"
        }

        let path = base.contains("/backend-api") ? "/wham/usage" : "/api/codex/usage"
        return URL(string: base + path) ?? URL(string: self.usageDefaultBase + "/wham/usage")!
    }

    private static func parseChatGPTBaseURL(from contents: String) -> String? {
        for rawLine in contents.split(whereSeparator: \.isNewline) {
            let line = rawLine.split(separator: "#", maxSplits: 1, omittingEmptySubsequences: true).first
                .map(String.init) ?? ""
            let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !trimmed.isEmpty else { continue }

            let parts = trimmed.split(separator: "=", maxSplits: 1, omittingEmptySubsequences: true)
            guard parts.count == 2 else { continue }
            guard parts[0].trimmingCharacters(in: .whitespacesAndNewlines) == "chatgpt_base_url" else { continue }

            var value = parts[1].trimmingCharacters(in: .whitespacesAndNewlines)
            if value.hasPrefix("\""), value.hasSuffix("\""), value.count >= 2 {
                value = String(value.dropFirst().dropLast())
            }
            if value.hasPrefix("'"), value.hasSuffix("'"), value.count >= 2 {
                value = String(value.dropFirst().dropLast())
            }
            return value
        }

        return nil
    }

    private static func extractErrorCode(from data: Data) -> String? {
        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return nil
        }
        if let error = json["error"] as? [String: Any] {
            return error["code"] as? String
        }
        if let error = json["error"] as? String {
            return error
        }
        return json["code"] as? String
    }

    private static func makeWindow(_ value: UsageWindowResponse) -> UsageWindowSnapshot {
        UsageWindowSnapshot(
            usedPercent: value.usedPercent,
            resetAt: Date(timeIntervalSince1970: TimeInterval(value.resetAt)),
            limitWindowSeconds: value.limitWindowSeconds)
    }

    private static func makeCredits(_ value: CreditDetails) -> CreditsBalanceSnapshot {
        CreditsBalanceSnapshot(
            hasCredits: value.hasCredits,
            unlimited: value.unlimited,
            balance: value.balance)
    }

    private static func isEquivalent(_ lhs: AccountUsageSnapshot, _ rhs: AccountUsageSnapshot) -> Bool {
        self.normalizeString(lhs.email)?.lowercased() == self.normalizeString(rhs.email)?.lowercased()
            && self.normalizeString(lhs.providerAccountID) == self.normalizeString(rhs.providerAccountID)
            && self.normalizeString(lhs.plan) == self.normalizeString(rhs.plan)
            && lhs.allowed == rhs.allowed
            && lhs.limitReached == rhs.limitReached
            && self.windowsEquivalent(lhs.primaryWindow, rhs.primaryWindow)
            && self.windowsEquivalent(lhs.secondaryWindow, rhs.secondaryWindow)
            && self.creditsEquivalent(lhs.credits, rhs.credits)
    }

    private static func windowsEquivalent(_ lhs: UsageWindowSnapshot?, _ rhs: UsageWindowSnapshot?) -> Bool {
        switch (lhs, rhs) {
        case (.none, .none):
            return true
        case let (.some(left), .some(right)):
            let resetAtMatches: Bool
            switch (left.resetAt, right.resetAt) {
            case (.none, .none):
                resetAtMatches = true
            case let (.some(leftResetAt), .some(rightResetAt)):
                resetAtMatches = abs(leftResetAt.timeIntervalSince(rightResetAt)) <= 1
            default:
                resetAtMatches = false
            }

            return left.limitWindowSeconds == right.limitWindowSeconds
                && resetAtMatches
                && abs(left.usedPercent - right.usedPercent) < 0.001
        default:
            return false
        }
    }

    private static func creditsEquivalent(_ lhs: CreditsBalanceSnapshot?, _ rhs: CreditsBalanceSnapshot?) -> Bool {
        switch (lhs, rhs) {
        case (.none, .none):
            return true
        case let (.some(left), .some(right)):
            let balancesMatch: Bool
            switch (left.balance, right.balance) {
            case (.none, .none):
                balancesMatch = true
            case let (.some(leftBalance), .some(rightBalance)):
                balancesMatch = abs(leftBalance - rightBalance) < 0.001
            default:
                balancesMatch = false
            }

            return left.hasCredits == right.hasCredits
                && left.unlimited == right.unlimited
                && balancesMatch
        default:
            return false
        }
    }

    private static func makeNormalizedWindows(_ rateLimit: RateLimitDetails?) -> (primary: UsageWindowSnapshot?, secondary: UsageWindowSnapshot?) {
        guard let rateLimit else {
            return (nil, nil)
        }

        return self.normalizeWindowRoles(
            primary: rateLimit.primaryWindow.map(self.makeWindow),
            secondary: rateLimit.secondaryWindow.map(self.makeWindow))
    }

    private static func normalizeWindowRoles(
        primary: UsageWindowSnapshot?,
        secondary: UsageWindowSnapshot?)
        -> (primary: UsageWindowSnapshot?, secondary: UsageWindowSnapshot?)
    {
        switch (primary, secondary) {
        case let (.some(primaryWindow), .some(secondaryWindow)):
            switch (self.role(for: primaryWindow), self.role(for: secondaryWindow)) {
            case (.session, .weekly), (.session, .unknown), (.unknown, .weekly):
                return (primaryWindow, secondaryWindow)
            case (.weekly, .session), (.weekly, .unknown):
                return (secondaryWindow, primaryWindow)
            default:
                return (primaryWindow, secondaryWindow)
            }
        case let (.some(primaryWindow), .none):
            switch self.role(for: primaryWindow) {
            case .weekly:
                return (nil, primaryWindow)
            case .session, .unknown:
                return (primaryWindow, nil)
            }
        case let (.none, .some(secondaryWindow)):
            switch self.role(for: secondaryWindow) {
            case .weekly:
                return (nil, secondaryWindow)
            case .session, .unknown:
                return (secondaryWindow, nil)
            }
        case (.none, .none):
            return (nil, nil)
        }
    }

    private enum WindowRole {
        case session
        case weekly
        case unknown
    }

    private static func role(for window: UsageWindowSnapshot) -> WindowRole {
        switch window.limitWindowSeconds {
        case 18_000:
            return .session
        case 604_800:
            return .weekly
        default:
            return .unknown
        }
    }

    private static func parseDate(_ raw: Any?) -> Date? {
        guard let value = raw as? String, !value.isEmpty else {
            return nil
        }

        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = formatter.date(from: value) {
            return date
        }

        formatter.formatOptions = [.withInternetDateTime]
        return formatter.date(from: value)
    }

    private static func stringValue(in dictionary: [String: Any], key: String) -> String? {
        if let value = dictionary[key] as? String, !value.isEmpty {
            return value
        }

        let camelKey = key
            .split(separator: "_")
            .enumerated()
            .map { index, piece in
                if index == 0 {
                    return piece.lowercased()
                }
                return piece.prefix(1).uppercased() + piece.dropFirst().lowercased()
            }
            .joined()

        if let value = dictionary[camelKey] as? String, !value.isEmpty {
            return value
        }

        return nil
    }

    private static func normalizeString(_ value: String?) -> String? {
        guard let value = value?.trimmingCharacters(in: .whitespacesAndNewlines), !value.isEmpty else {
            return nil
        }
        return value
    }

    private static func parseJWT(_ token: String) -> [String: Any]? {
        let parts = token.split(separator: ".")
        guard parts.count >= 2 else {
            return nil
        }

        var payload = String(parts[1])
            .replacingOccurrences(of: "-", with: "+")
            .replacingOccurrences(of: "_", with: "/")
        while payload.count % 4 != 0 {
            payload.append("=")
        }

        guard let data = Data(base64Encoded: payload),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else {
            return nil
        }

        return json
    }
}
