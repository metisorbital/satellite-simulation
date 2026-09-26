import { expect, test } from '@playwright/test';
import { demoOperator, statusAt } from '../fixtures';

test('first visit auto-login, failed connection retry, reload, and switching operators', async ({ page }) => {
  let session: Record<string, any> | null = null;
  let lastLogin: Record<string, any> | undefined;
  let logoutToken: string | undefined;
  let runReads = 0;
  let failLogin = true;
  let loginCount = 0;
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/v1/viewer/session', route => route.fulfill(session
    ? { json: session }
    : { status: 401, json: { message: 'Log in to continue.' } }));
  await page.route('**/v1/datasets', route => route.fulfill({ json: { items: [] } }));
  await page.route('**/v1/viewer/login', async route => {
    lastLogin = route.request().postDataJSON();
    loginCount++;
    if (failLogin) {
      return route.fulfill({ status: 503, json: { message: 'Service unavailable.' } });
    }
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
  await expect(page.getByText('Could not open the operator workspace. Check the connection and try again.', { exact: true })).toBeVisible();
  await expect(page.locator('#metis-earth')).toHaveCount(0);
  expect(runReads).toBe(0);
  expect(lastLogin).toEqual({ login: 'operator1', password: 'demo' });
  failLogin = false;
  await page.getByRole('button', { name: 'Retry', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Operator Operator One, operator1', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Mission overview', exact: true })).toBeVisible();
  expect(loginCount).toBe(2);
  await page.reload();
  await page.getByRole('button', { name: 'Operator Operator One, operator1', exact: true }).click();
  expect(loginCount).toBe(2);
  await page.getByRole('menuitem', { name: 'operator2', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Operator Operator Two, operator2', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Operator Operator One, operator1', exact: true })).toHaveCount(0);
  expect(logoutToken).toBe('csrf-operator1');
  expect(lastLogin).toEqual({ login: 'operator2', password: 'demo' });
  await page.reload();
  await expect(page.getByRole('button', { name: 'Operator Operator Two, operator2', exact: true })).toBeVisible();
  expect(loginCount).toBe(3);
  expect(session!.run.run_id).toBe('run-operator2');
  expect(errors).toEqual([]);
});

test('workspace connection retry remains usable on a narrow viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  let sessionReads = 0;
  await page.route('**/v1/viewer/session', route => {
    sessionReads++;
    return route.fulfill({ status: 503, json: { message: 'Service unavailable.' } });
  });
  await page.goto('/');
  await expect(page.getByText('Could not open the operator workspace. Check the connection and try again.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Retry', exact: true }).click();
  await expect.poll(() => sessionReads).toBe(2);
  await expect(page.getByRole('button', { name: 'Retry', exact: true })).toBeVisible();
  await page.screenshot({ path: 'artifacts/operator-retry-mobile.png' });
});
