import { test, expect } from '@playwright/test';

const risksPayload = [
  {
    id: 99,
    ward_name: 'Westlands',
    village_name: 'Kangemi',
    hazard_type: 'flood',
    risk_level: 'critical',
    risk_score: 92.5,
    guidance_en: 'Move to higher ground immediately.',
    guidance_sw: 'Nenda sehemu ya juu mara moja.',
    summary: 'Critical flood risk in low-lying zones.',
    issued_at: new Date().toISOString(),
    latitude: -1.267,
    longitude: 36.805,
  },
];

const heatmapPayload = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      geometry: {
        type: 'Polygon',
        coordinates: [[[36.779, -1.249], [36.836, -1.249], [36.836, -1.286], [36.779, -1.286], [36.779, -1.249]]],
      },
      properties: {
        ward_name: 'Westlands',
        county_name: 'Nairobi',
        risk_level: 'critical',
        risk_score: 92.5,
        hazard_type: 'flood',
        issued_at: new Date().toISOString(),
      },
    },
  ],
};

test.beforeEach(async ({ page }) => {
  await page.route('**/api/hazards/risks/?ward=*', async (route) => {
    await route.fulfill({ status: 200, body: JSON.stringify(risksPayload) });
  });

  await page.route('**/api/hazards/risks/ward-heatmap/**', async (route) => {
    await route.fulfill({ status: 200, body: JSON.stringify(heatmapPayload) });
  });

  await page.route('**/api/hazards/risks/events/**', async (route) => {
    await route.fulfill({ status: 200, body: '' });
  });
});

test('renders onboarding and then mobile SOS button', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByText('Welcome to Safeguard AI')).toBeVisible();
  await page.getByPlaceholder('e.g. Westlands').fill('Westlands');
  await page.getByRole('button', { name: 'Continue' }).click();
  await page.getByRole('button', { name: 'Continue' }).click();
  await page.getByPlaceholder('+2547XXXXXXXX').fill('+254700123456');
  await page.getByRole('button', { name: 'Finish' }).click();

  await expect(page.getByText('Ward: Westlands')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Sign in to Enable SOS' })).toBeVisible();
});
