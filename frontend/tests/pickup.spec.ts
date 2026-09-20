import { test, expect, type Page } from "@playwright/test";

async function chooseRoute(page: Page) {
  await page.getByLabel("Starting from").fill("E7 north corridor");
  await page.getByLabel("Going to").fill("Room 6004");
}

test("guides a user from onboarding to an editable route", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  const routePanel = page.getByRole("complementary", { name: "Your route" });
  await expect(routePanel).toBeVisible();
  await expect(page.getByLabel("Starting from")).toHaveValue("");
  await expect(page.getByLabel("Going to")).toHaveValue("");
  await chooseRoute(page);
  await expect(page.getByRole("heading", { name: "Ready to go" })).toBeVisible();
  await expect(page.getByLabel("Starting from")).toHaveValue("E7 north corridor");
  await expect(page.getByLabel("Going to")).toHaveValue("Room 6004");
  const initialDragCoordinates = await page.locator(".map-transform").evaluate((element) => {
    const matrix = (element as SVGGElement).getScreenCTM()!;
    const screenPoint = (x: number, y: number) => new DOMPoint(x, y).matrixTransform(matrix);
    return { from: screenPoint(1616, 1704), to: screenPoint(1279, 1961) };
  });
  await page.mouse.move(initialDragCoordinates.from.x, initialDragCoordinates.from.y);
  await page.mouse.down();
  await page.mouse.move(initialDragCoordinates.to.x, initialDragCoordinates.to.y, { steps: 8 });
  await page.mouse.up();
  await expect(page.getByLabel("Going to")).toHaveValue("Room 6007");
  await expect(page.getByText(/m · scroll to zoom/)).toBeVisible();
  await expect(page.locator(".end-route")).toHaveAttribute("marker-mid", "url(#route-arrow)");
  await page.getByRole("button", { name: "Zoom out" }).click();
  await page.getByRole("button", { name: "Zoom out" }).click();
  await page.getByRole("button", { name: "Zoom out" }).click();
  const dragCoordinates = await page.locator(".map-transform").evaluate((element) => {
    const matrix = (element as SVGGElement).getScreenCTM()!;
    const screenPoint = (x: number, y: number) => new DOMPoint(x, y).matrixTransform(matrix);
    return { from: screenPoint(1279, 1961), to: screenPoint(1626, 2213) };
  });
  await page.mouse.move(dragCoordinates.from.x, dragCoordinates.from.y);
  await page.mouse.down();
  await expect(page.locator(".endpoint-marker.is-dragging")).toHaveCount(1);
  await expect(page.locator(".endpoint-drag-hint")).toContainText("Drop END");
  await page.mouse.move(dragCoordinates.to.x, dragCoordinates.to.y, { steps: 8 });
  await expect(page.locator(".map-stop.is-nearest")).toHaveCount(1);
  await expect(page.getByLabel("Going to")).toHaveValue("Room 6007");
  await page.mouse.up();
  await expect(page.getByLabel("Going to")).toHaveValue("Room 6008");
  await expect(page.locator(".endpoint-marker.is-dragging")).toHaveCount(0);
  const map = page.locator(".campus-svg");
  const transformBeforeWheel = await page.locator(".map-transform").getAttribute("transform");
  await map.hover({ position: { x: 350, y: 300 } });
  await page.mouse.wheel(0, -220);
  await expect.poll(() => page.locator(".map-transform").getAttribute("transform")).not.toBe(transformBeforeWheel);
  const transformBeforeDrag = await page.locator(".map-transform").getAttribute("transform");
  await page.mouse.move(350, 300);
  await page.mouse.down();
  await page.mouse.move(430, 350, { steps: 4 });
  await page.mouse.up();
  await expect.poll(() => page.locator(".map-transform").getAttribute("transform")).not.toBe(transformBeforeDrag);
  expect(errors).toEqual([]);
});

test("intro opens from the FLIH menu instead of on page load", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Get there with FLIH." })).toHaveCount(0);
  await page.getByRole("button", { name: /FLIH/ }).hover();
  await expect(page.getByRole("button", { name: "what is flih?" })).toBeVisible();
  await page.getByRole("button", { name: "what is flih?" }).click();
  await expect(page.getByRole("heading", { name: "Get there with FLIH." })).toBeVisible();
  await page.getByRole("button", { name: "Got it" }).click();
  await expect(page.getByRole("heading", { name: "Get there with FLIH." })).toHaveCount(0);
});

test("a waypoint click opens route actions", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "View details for Room 6004" }).click();
  const details = page.getByRole("region", { name: "Room 6004 waypoint details" });
  await expect(details).toBeVisible();
  await expect(details.getByRole("button", { name: "Set as end" })).toBeVisible();
  const positionBeforeZoom = await details.boundingBox();
  await page.getByRole("button", { name: "Zoom out" }).click();
  await expect(details).toBeVisible();
  await expect.poll(async () => (await details.boundingBox())?.x).not.toBe(positionBeforeZoom?.x);
  await details.getByRole("button", { name: "Set as start" }).click();
  await expect(page.getByLabel("Starting from")).toHaveValue("Room 6004");
  await page.locator(".campus-svg").click({ position: { x: 10, y: 10 } });
  await expect(details).toHaveCount(0);
});

test("mobile route panel fits the viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await chooseRoute(page);
  await expect(page.getByRole("complementary", { name: "Your route" })).toBeVisible();
  const overflow = await page.evaluate(() =>
    Array.from(document.querySelectorAll("body *:not(svg *)"))
      .filter((element) => {
        const box = element.getBoundingClientRect();
        return box.right > window.innerWidth + 1 && box.width > 0;
      })
      .map((element) => element.className)
      .slice(0, 10),
  );
  expect(overflow).toEqual([]);
  const initialTransform = await page.locator(".map-transform").getAttribute("transform");
  await page.getByRole("button", { name: "Zoom in" }).click();
  await expect.poll(() => page.locator(".map-transform").getAttribute("transform")).not.toBe(initialTransform);
});

test("queue requests no longer require a captcha", async ({ request }) => {
  const username = `test_${Date.now().toString().slice(-8)}`;
  const join = await request.post("/api/flih", { data: { username, pickup: "dc", end: "e7" } });
  expect(join.status()).toBe(200);
  expect(await join.json()).toEqual({ ok: true });
  const telemetry = await request.patch("/api/flih", { data: { x: 1, y: 1, battery: 80, status: "available" } });
  expect(telemetry.status()).toBe(401);
});

test("an active guide request keeps route edits after dropping a marker", async ({ page }) => {
  await page.goto("/");
  await chooseRoute(page);
  const routePanel = page.getByRole("complementary", { name: "Your route" });
  await page.getByLabel("Your name").fill(`route_${Date.now().toString().slice(-7)}`);
  await page.getByRole("button", { name: /Request guide/ }).click();
  await expect(page.getByText("Guide requested", { exact: true })).toBeVisible();

  const dragCoordinates = await page.locator(".map-transform").evaluate((element) => {
    const matrix = (element as SVGGElement).getScreenCTM()!;
    const screenPoint = (x: number, y: number) => new DOMPoint(x, y).matrixTransform(matrix);
    return { from: screenPoint(1616, 1704), to: screenPoint(1279, 1961) };
  });
  await page.mouse.move(dragCoordinates.from.x, dragCoordinates.from.y);
  await page.mouse.down();
  await page.mouse.move(dragCoordinates.to.x, dragCoordinates.to.y, { steps: 8 });
  await page.mouse.up();
  await expect(page.getByLabel("Going to")).toHaveValue("Room 6007");
  await page.waitForTimeout(5_100);
  await expect(page.getByLabel("Going to")).toHaveValue("Room 6007");
});
