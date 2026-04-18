import SwiftUI

@main
struct CodexControlApp: App {
    @StateObject private var model = AppModel()

    var body: some Scene {
        MenuBarExtra {
            RootView(model: self.model)
        } label: {
            HStack(spacing: 0) {
                Image(systemName: self.model.menuBarSymbol)
            }
            .foregroundStyle(Color(nsColor: self.model.menuBarSymbolColor))
        }
        .menuBarExtraStyle(.window)
    }
}
