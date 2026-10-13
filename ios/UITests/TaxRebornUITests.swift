import XCTest

final class TaxRebornUITests: XCTestCase {
    private let app = XCUIApplication()
    private func tap(_ name: String, timeout: TimeInterval = 120) {
        let buttons = app.buttons.matching(identifier: name)
        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline {
            if let button = buttons.allElementsBoundByIndex.first(where: { $0.isHittable }) { button.tap(); return }
            RunLoop.current.run(until: Date().addingTimeInterval(0.25))
        }
        XCTFail("No visible button: " + name)
    }
    private func screenshot(_ name: String) {
        let image = XCTAttachment(screenshot: app.screenshot())
        image.name = name; image.lifetime = .keepAlways; add(image)
    }
    override func tearDown() {
        screenshot("iOS-final-test-window")
        let hierarchy = XCTAttachment(string: app.debugDescription)
        hierarchy.name = "iOS-real-accessibility-hierarchy"; hierarchy.lifetime = .keepAlways; add(hierarchy)
        super.tearDown()
    }
    func testCalculationSaveAndReopen() {
        continueAfterFailure = false
        app.launch()
        XCTAssertTrue(app.staticTexts["Let's start with you."].waitForExistence(timeout: 180))
        tap("Open tax navigator"); tap("My returns")
        tap("Synthetic examples"); tap("Open example")
        XCTAssertTrue(app.staticTexts["$1,413"].firstMatch.waitForExistence(timeout: 180))
        screenshot("iOS-real-calculation-1413")
        tap("Save")
        XCTAssertTrue(app.staticTexts["Saved on this device"].waitForExistence(timeout: 120))
        tap("Open tax navigator"); tap("Wages & salaries · W-2")
        let withholding = app.webViews.textFields["Box 2 · Federal income tax withheld"]
        if !withholding.isHittable { app.swipeUp() }
        XCTAssertTrue(withholding.waitForExistence(timeout: 30))
        withholding.tap()
        // A center tap can place the caret before the last digit. Explicitly
        // select the complete existing value rather than deleting from a caret.
        withholding.press(forDuration: 1.2)
        let all = app.buttons["Select All"].firstMatch
        if all.waitForExistence(timeout: 10) && all.isHittable { all.tap() }
        else {
            let menu = app.menuItems["Select All"].firstMatch
            XCTAssertTrue(menu.waitForExistence(timeout: 10)); menu.tap()
        }
        withholding.typeText("7000")
        XCTAssertEqual(withholding.value as? String, "7000", "Real native input must contain exactly the intended withholding")
        screenshot("iOS-real-withholding-entry-7000")
        let done = app.toolbars.buttons["Done"].firstMatch
        if done.isHittable { done.tap() }
        // Move focus so the real input/change handlers recalculate.
        tap("Save")
        XCTAssertTrue(app.staticTexts["$1,913"].firstMatch.waitForExistence(timeout: 120))
        screenshot("iOS-edited-and-saved-1913")
        app.terminate(); app.launch()
        XCTAssertTrue(app.staticTexts["Let's start with you."].waitForExistence(timeout: 180))
        tap("Open tax navigator"); tap("My returns"); tap("Open")
        XCTAssertTrue(app.staticTexts["$1,913"].firstMatch.waitForExistence(timeout: 180))
        screenshot("iOS-reopened-persistent-return-1913")
        XCTAssertTrue(app.buttons["native-add-document"].exists)
    }
}
