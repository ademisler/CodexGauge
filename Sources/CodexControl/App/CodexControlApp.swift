import SwiftUI

@main
struct CodexControlApp: App {
    @StateObject private var model = AppModel()
    @StateObject private var appUpdater = AppUpdater()

    var body: some Scene {
        MenuBarExtra {
            RootView(model: self.model, appUpdater: self.appUpdater)
        } label: {
            HStack(spacing: 0) {
                Image(systemName: self.model.menuBarSymbol)
            }
            .foregroundStyle(Color(nsColor: self.model.menuBarSymbolColor))
        }
        .menuBarExtraStyle(.window)
    }
}
