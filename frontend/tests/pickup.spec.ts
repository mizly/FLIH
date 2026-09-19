import { test, expect } from "@playwright/test";

test("anonymous pickup, failed captcha, shared queue, persistence, and cancellation", async ({
  page,
  browser,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Join the queue", exact: true }),
  ).toBeEnabled();
  await page.screenshot({ path: "test-results/desktop.png", fullPage: true });
  await page.getByLabel("What should we call you?").fill("test_human");
  await page
    .getByRole("button", { name: "Join the queue", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.locator(".challenge-question")).toContainText(
    "existential",
  );
  await page.getByLabel("Your answer").fill("999");
  await page
    .getByRole("button", { name: "I think, therefore I queue" })
    .click();
  await expect(page.locator(".error-message")).toContainText("Not quite");
  await expect(page.locator(".challenge-question")).toContainText(
    "existential",
  );
  const question = await page.locator(".challenge-question").innerText();
  const numbers = question.match(/\d+/g)!.map(Number);
  await page.getByLabel("Your answer").fill(String(numbers[0] + numbers[1]));
  await page
    .getByRole("button", { name: "I think, therefore I queue" })
    .click();
  await expect(
    page.getByRole("heading", { name: "You’re on the list!" }),
  ).toBeVisible();
  const visitor = await browser.newContext();
  const visitorPage = await visitor.newPage();
  await visitorPage.goto("/");
  await expect(visitorPage.locator(".queue-list")).toContainText("test_human");
  await expect(
    visitorPage.getByRole("button", { name: "Join the queue", exact: true }),
  ).toBeEnabled();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "You’re on the list!" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Leave the queue" }).click();
  await expect(
    page.getByRole("button", { name: "Join the queue", exact: true }),
  ).toBeVisible();
  await visitorPage.reload();
  await expect(visitorPage.locator(".queue-list")).not.toBeVisible();
  await visitor.close();
  expect(errors).toEqual([]);
});

test("mobile layout and navigation, map controls, invalid route", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Join the queue", exact: true }),
  ).toBeEnabled();
  await page.screenshot({ path: "test-results/mobile.png", fullPage: true });
  const overflow = await page.evaluate(() =>
    Array.from(document.querySelectorAll("body *"))
      .filter((e) => {
        const box = e.getBoundingClientRect();
        return box.right > window.innerWidth + 1 && box.width > 0;
      })
      .slice(0, 15)
      .map((e) => ({
        tag: e.tagName,
        class: e.getAttribute("class"),
        width: e.getBoundingClientRect().width,
        right: e.getBoundingClientRect().right,
      })),
  );
  expect(overflow).toEqual([]);
  await page.getByRole("button", { name: "Zoom in", exact: true }).click();
  await expect(page.locator(".map-transform")).toHaveAttribute(
    "transform",
    /scale\(1.2\)/,
  );
  await page.getByRole("button", { name: "Center map on FLIH" }).click();
  await expect(page.locator(".map-transform")).toHaveAttribute(
    "transform",
    /scale\(1.3\)/,
  );
  await page.getByLabel("What should we call you?").fill("lost_goose");
  await page.getByLabel("Take me to").selectOption("slc");
  await page
    .getByRole("button", { name: "Join the queue", exact: true })
    .click();
  await expect(page.locator(".error-message")).toContainText(
    "different destination",
  );
  await page.getByRole("button", { name: "How it works", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Small brain. Simple plan." }),
  ).toBeInViewport();
});

test("server refuses unverified queue entries and unauthenticated hardware updates", async ({
  request,
}) => {
  const join = await request.post("/api/flih", {
    data: {
      username: "robot_spam",
      pickup: "slc",
      destination: "e7",
      answer: "1",
    },
  });
  expect(join.status()).toBe(400);
  expect((await join.json()).error).toContain("brain check");
  const telemetry = await request.patch("/api/flih", {
    data: { x: 1, y: 1, battery: 80, status: "available" },
  });
  expect(telemetry.status()).toBe(401);
});
