import { test, expect, type Page } from "@playwright/test";

async function completeWizard(page: Page) {
  await expect(page.getByRole("heading", { name: "Get there with FLIH." })).toBeVisible();
  await page.getByRole("button", { name: "Plan my route" }).click();
  await expect(page.getByRole("heading", { name: "Where are you now?" })).toBeVisible();
  await page.getByRole("radio", { name: /E7 north/i }).click();
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByRole("heading", { name: "Where do you want to go?" })).toBeVisible();
  await page.getByRole("radio", { name: /6004/i }).click();
  await page.getByRole("button", { name: "Show my route" }).click();
}

test("guides a user from onboarding to an editable route", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await completeWizard(page);
  const collapsedPanel = page.getByRole("complementary", { name: "Your route" });
  await expect(collapsedPanel).toHaveCSS("width", "60px");
  await collapsedPanel.hover();
  await expect(page.getByRole("heading", { name: "Ready to go" })).toBeVisible();
  await expect(page.getByLabel("Starting from")).toHaveValue("dc");
  await expect(page.getByLabel("Going to")).toHaveValue("e7");
  const initialDragCoordinates = await page.locator(".map-transform").evaluate((element) => {
    const matrix = (element as SVGGElement).getScreenCTM()!;
    const screenPoint = (x: number, y: number) => new DOMPoint(x, y).matrixTransform(matrix);
    return { from: screenPoint(1485, 1725), to: screenPoint(1485, 1955) };
  });
  await page.mouse.move(initialDragCoordinates.from.x, initialDragCoordinates.from.y);
  await page.mouse.down();
  await page.mouse.move(initialDragCoordinates.to.x, initialDragCoordinates.to.y, { steps: 8 });
  await page.mouse.up();
  await expect(page.getByLabel("Going to")).toHaveValue("r6007");
  await expect(page.getByText(/m · scroll to zoom/)).toBeVisible();
  await expect(page.locator(".destination-route")).toHaveAttribute("marker-mid", "url(#route-arrow)");
  await page.getByRole("button", { name: "Zoom out" }).click();
  await page.getByRole("button", { name: "Zoom out" }).click();
  await page.getByRole("button", { name: "Zoom out" }).click();
  const dragCoordinates = await page.locator(".map-transform").evaluate((element) => {
    const matrix = (element as SVGGElement).getScreenCTM()!;
    const screenPoint = (x: number, y: number) => new DOMPoint(x, y).matrixTransform(matrix);
    return { from: screenPoint(1485, 1955), to: screenPoint(1485, 2215) };
  });
  await page.mouse.move(dragCoordinates.from.x, dragCoordinates.from.y);
  await page.mouse.down();
  await expect(page.locator(".endpoint-marker.is-dragging")).toHaveCount(1);
  await expect(page.locator(".endpoint-drag-hint")).toContainText("Drop END");
  await page.mouse.move(dragCoordinates.to.x, dragCoordinates.to.y, { steps: 8 });
  await expect(page.locator(".map-stop.is-nearest")).toHaveCount(1);
  await expect(page.getByLabel("Going to")).toHaveValue("r6007");
  await page.mouse.up();
  await expect(page.getByLabel("Going to")).toHaveValue("r6008");
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

test("mobile wizard and route panel fit the viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await completeWizard(page);
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
  const join = await request.post("/api/flih", { data: { username, pickup: "dc", destination: "e7" } });
  expect(join.status()).toBe(200);
  expect(await join.json()).toEqual({ ok: true });
  const telemetry = await request.patch("/api/flih", { data: { x: 1, y: 1, battery: 80, status: "available" } });
  expect(telemetry.status()).toBe(401);
});

test("an active guide request keeps route edits after dropping a marker", async ({ page }) => {
  await page.goto("/");
  await completeWizard(page);
  const routePanel = page.getByRole("complementary", { name: "Your route" });
  await routePanel.hover();
  await page.getByLabel("Your name").fill(`route_${Date.now().toString().slice(-7)}`);
  await page.getByRole("button", { name: /Request guide/ }).click();
  await expect(page.getByText("Guide requested", { exact: true })).toBeVisible();

  const dragCoordinates = await page.locator(".map-transform").evaluate((element) => {
    const matrix = (element as SVGGElement).getScreenCTM()!;
    const screenPoint = (x: number, y: number) => new DOMPoint(x, y).matrixTransform(matrix);
    return { from: screenPoint(1485, 1725), to: screenPoint(1485, 1955) };
  });
  await page.mouse.move(dragCoordinates.from.x, dragCoordinates.from.y);
  await page.mouse.down();
  await page.mouse.move(dragCoordinates.to.x, dragCoordinates.to.y, { steps: 8 });
  await page.mouse.up();
  await expect(page.getByLabel("Going to")).toHaveValue("r6007");
  await page.waitForTimeout(5_100);
  await expect(page.getByLabel("Going to")).toHaveValue("r6007");
});
