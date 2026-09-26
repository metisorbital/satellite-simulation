import { expect, test, type Page } from '@playwright/test';
import { demoOperator, statusAt } from '../fixtures';

async function enter(page: Page, name: string, value: string): Promise<void> {
  const field = page.getByRole('textbox', { name: new RegExp(`^${name}(?: |$)`) });
  await field.click();
  await expect(field).toBeFocused();
  // DOM focus precedes Flutter's editing connection. Wait for the framework
  // frame before typing so its initial editing value cannot overwrite input.
  await page.evaluate(() => new Promise<void>(resolve =>
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  if (name === 'Password') await expect(field).toHaveAttribute('autocapitalize', 'off');
  await page.keyboard.press('ControlOrMeta+A');
  await page.keyboard.type(value, { delay: 25 });
  await expect(field).toHaveValue(value);
}

test('first visit, failed login, reload, logout, and switching operators', async ({ page }) => {
  let session: Record<string, any> | null = null;
  let lastLogin: Record<string, any> | undefined;
  let logoutToken: string | undefined;
  let runReads = 0;
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/v1/viewer/session', route => route.fulfill(session
    ? { json: session }
    : { status: 401, json: { message: 'Log in to continue.' } }));
  await page.route('**/v1/viewer/login', async route => {
    lastLogin = route.request().postDataJSON();
    if (!['operator1', 'operator2'].includes(lastLogin!.login)) {
      return route.fulfill({ status: 422, json: { message: 'Choose a listed demo operator.' } });
    }
    const login = lastLogin!.login;
    session = {
      csrf_token: `csrf-${login}`, allowed_actions: ['start', 'pause', 'resume', 'set_speed', 'stop'],
      operator: { ...demoOperator, login, display_name: login === 'operator1' ? 'Operator One' : 'Operator Two',
        user_id: login === 'operator1' ? demoOperator.user_id : '22222222-2222-4222-8222-222222222222' },
      run: { ...statusAt(-1, 'created', 1), run_id: `run-${login}`,
        satellites: statusAt(-1).satellites.map((satellite: Record<string, any>) => ({
          ...satellite, name: `${login} spacecraft`, stream_id: `${login}-${satellite.stream_id}`,
        })) },
    };
    return route.fulfill({ json: session });
  });
  await page.route('**/v1/viewer/logout', route => {
    logoutToken = route.request().headers()['x-csrf-token'];
    session = null;
    return route.fulfill({ json: {} });
  });
  await page.route('**/v1/viewer/configuration', route => route.fulfill({ json: { satellites: [] } }));
  await page.route('**/v1/runs/*/snapshot?history=41', route => {
    runReads++;
    return route.fulfill({ json: { status: session!.run, frames: [] } });
  });
  await page.routeWebSocket('**/v1/runs/*/visual', () => {});

  await page.goto('/');
  await expect(page.getByText('Operator login', { exact: true })).toBeVisible();
  await expect(page.locator('#metis-earth')).toHaveCount(0);
  expect(runReads).toBe(0);
  await enter(page, 'Login', 'unknown');
  await enter(page, 'Password', 'demo-only');
  await expect(page.locator('input[type=password]')).toHaveCount(1);
  await page.getByRole('button', { name: 'Log in', exact: true }).click();
  await expect(page.locator('flt-semantics span').filter({ hasText: /^Choose a listed demo operator\.$/ })).toBeVisible();
  await enter(page, 'Login', 'operator1');
  await enter(page, 'Password', 'demo-only');
  await page.getByRole('textbox', { name: 'Password', exact: true }).press('Enter');
  await expect(page.getByText('Operator One · operator1', { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Orbital overview', exact: true })).toBeVisible();
  expect(lastLogin).toEqual({ login: 'operator1', password: 'demo-only' });
  await page.reload();
  await expect(page.getByText('Operator One · operator1', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: /Log out/ }).click();
  await expect(page.getByText('Operator login', { exact: true })).toBeVisible();
  expect(logoutToken).toBe('csrf-operator1');
  await expect(page.locator('#metis-earth')).toHaveCount(0);
  await expect(page.getByRole('textbox', { name: 'Password', exact: true })).toHaveValue('');
  const readsAtLogout = runReads;
  await page.reload();
  await expect(page.getByText('Operator login', { exact: true })).toBeVisible();
  expect(runReads).toBe(readsAtLogout);
  await enter(page, 'Login', 'operator2');
  await enter(page, 'Password', 'another-demo-password');
  await page.getByRole('button', { name: 'Log in', exact: true }).click();
  await expect(page.getByText('Operator Two · operator2', { exact: true })).toBeVisible();
  await expect(page.getByText('Operator One · operator1', { exact: true })).toHaveCount(0);
  expect(session!.run.run_id).toBe('run-operator2');
  expect(errors).toEqual([]);
});

test('login panel remains usable on a narrow viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route('**/v1/viewer/session', route => route.fulfill({ status: 401, json: { message: 'Log in.' } }));
  await page.goto('/');
  await expect(page.getByText('Operator login', { exact: true })).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Login', exact: true })).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Password', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Log in', exact: true })).toBeVisible();
  await page.screenshot({ path: 'artifacts/operator-login-mobile.png' });
});
