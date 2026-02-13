import { chromium } from 'playwright';

const BASE = 'http://localhost:3000';
const SCREENSHOT_DIR = '/Users/will/Documents/Projects/MadLibs';

(async () => {
  const browser = await chromium.launch({ headless: true });

  // --- Context 1: Host ---
  const hostContext = await browser.newContext();
  const hostPage = await hostContext.newPage();
  hostPage.setDefaultTimeout(15000);

  console.log('=== STEP 1: Host creates a room ===');
  await hostPage.goto(BASE);
  await hostPage.waitForLoadState('networkidle');

  // Click Multiplayer
  const multiplayerBtn = hostPage.getByRole('button', { name: /multiplayer/i })
    .or(hostPage.locator('text=Multiplayer'))
    .or(hostPage.locator('a:has-text("Multiplayer")'));
  await multiplayerBtn.first().click();
  await hostPage.waitForLoadState('networkidle');
  console.log('  Clicked Multiplayer. URL:', hostPage.url());
  await hostPage.screenshot({ path: `${SCREENSHOT_DIR}/01-multiplayer-page.png`, fullPage: true });

  // Click Create Room
  const createBtn = hostPage.getByRole('button', { name: /create/i })
    .or(hostPage.locator('text=Create Room'))
    .or(hostPage.locator('a:has-text("Create")'));
  await createBtn.first().click();
  await hostPage.waitForLoadState('networkidle');
  console.log('  Clicked Create Room. URL:', hostPage.url());
  await hostPage.screenshot({ path: `${SCREENSHOT_DIR}/02-create-room-page.png`, fullPage: true });

  // Select a template - click the first one available
  const templateCard = hostPage.locator('[data-testid="template-card"], .template-card, [class*="template"], [class*="card"]').first();
  if (await templateCard.isVisible().catch(() => false)) {
    await templateCard.click();
    console.log('  Clicked template card');
  } else {
    const anyTemplate = hostPage.locator('button, a, [role="button"]').filter({ hasText: /template|story|adventure|classic/i }).first();
    if (await anyTemplate.isVisible().catch(() => false)) {
      await anyTemplate.click();
      console.log('  Clicked template option');
    }
  }
  await hostPage.waitForLoadState('networkidle');
  await hostPage.screenshot({ path: `${SCREENSHOT_DIR}/03-after-template-select.png`, fullPage: true });
  console.log('  After template select. URL:', hostPage.url());

  // Look for a proceed/continue/create/start button
  const proceedBtn = hostPage.getByRole('button', { name: /proceed|continue|create|start|next|go/i }).first();
  if (await proceedBtn.isVisible().catch(() => false)) {
    await proceedBtn.click();
    await hostPage.waitForLoadState('networkidle');
    console.log('  Clicked proceed button');
  }

  // Wait for lobby
  await hostPage.waitForTimeout(2000);
  await hostPage.screenshot({ path: `${SCREENSHOT_DIR}/04-looking-for-lobby.png`, fullPage: true });
  console.log('  Current URL:', hostPage.url());

  // Extract room code
  const pageText = await hostPage.textContent('body');
  const codeMatch = pageText.match(/\b([A-Z0-9]{6})\b/);
  let roomCode = codeMatch ? codeMatch[1] : null;

  const urlMatch = hostPage.url().match(/\/room\/([A-Z0-9]+)/i);
  if (!roomCode && urlMatch) {
    roomCode = urlMatch[1].toUpperCase();
  }

  if (!roomCode) {
    const codeEl = hostPage.locator('[data-testid="room-code"], [class*="code"], [class*="room-code"]').first();
    if (await codeEl.isVisible().catch(() => false)) {
      roomCode = (await codeEl.textContent()).trim();
    }
  }

  console.log('  Room code found:', roomCode);

  // === STEP 2 ===
  console.log('\n=== STEP 2: Screenshot host lobby ===');
  await hostPage.screenshot({ path: `${SCREENSHOT_DIR}/05-host-lobby-live.png`, fullPage: true });

  if (!roomCode) {
    console.error('ERROR: Could not find room code. Dumping page content...');
    console.log(pageText.substring(0, 2000));
    await browser.close();
    process.exit(1);
  }

  // === STEP 3: Player joins ===
  console.log('\n=== STEP 3: Player joins room', roomCode, '===');
  const playerContext = await browser.newContext();
  const playerPage = await playerContext.newPage();
  playerPage.setDefaultTimeout(15000);

  await playerPage.goto(BASE);
  await playerPage.waitForLoadState('networkidle');

  const pMultiBtn = playerPage.getByRole('button', { name: /multiplayer/i })
    .or(playerPage.locator('text=Multiplayer'))
    .or(playerPage.locator('a:has-text("Multiplayer")'));
  await pMultiBtn.first().click();
  await playerPage.waitForLoadState('networkidle');
  console.log('  Player: Clicked Multiplayer. URL:', playerPage.url());

  const joinBtn = playerPage.getByRole('button', { name: /join/i })
    .or(playerPage.locator('text=Join Room'))
    .or(playerPage.locator('a:has-text("Join")'));
  await joinBtn.first().click();
  await playerPage.waitForLoadState('networkidle');
  console.log('  Player: Clicked Join Room. URL:', playerPage.url());
  await playerPage.screenshot({ path: `${SCREENSHOT_DIR}/06-player-join-page.png`, fullPage: true });

  const codeInput = playerPage.locator('input[type="text"], input[name*="code"], input[placeholder*="code" i], input[placeholder*="room" i]').first();
  await codeInput.fill(roomCode);

  const submitJoinBtn = playerPage.getByRole('button', { name: /join|enter|go|submit/i }).first();
  await submitJoinBtn.click();
  await playerPage.waitForLoadState('networkidle');
  await playerPage.waitForTimeout(2000);
  console.log('  Player: Submitted. URL:', playerPage.url());
  await playerPage.screenshot({ path: `${SCREENSHOT_DIR}/07-player-joined.png`, fullPage: true });

  // === STEP 4 ===
  console.log('\n=== STEP 4: Host checks player list ===');
  await hostPage.waitForTimeout(2000);
  await hostPage.screenshot({ path: `${SCREENSHOT_DIR}/08-host-lobby-2-players.png`, fullPage: true });
  const hostBodyText = await hostPage.textContent('body');
  console.log('  Host page text (first 1500 chars):', hostBodyText.substring(0, 1500));

  // === STEP 5 ===
  console.log('\n=== STEP 5: Host starts the game ===');
  const startBtn = hostPage.getByRole('button', { name: /start/i }).first();
  if (await startBtn.isVisible().catch(() => false)) {
    await startBtn.click();
    console.log('  Host: Clicked Start Game');
    await hostPage.waitForLoadState('networkidle');
    await hostPage.waitForTimeout(2000);
    await hostPage.screenshot({ path: `${SCREENSHOT_DIR}/09-host-after-start.png`, fullPage: true });
    console.log('  Host URL after start:', hostPage.url());
  } else {
    console.log('  WARNING: Start button not found.');
    await hostPage.screenshot({ path: `${SCREENSHOT_DIR}/09-host-no-start-btn.png`, fullPage: true });
  }

  // === STEP 6 ===
  console.log('\n=== STEP 6: Player checks for prompting page ===');
  await playerPage.waitForTimeout(3000);
  await playerPage.screenshot({ path: `${SCREENSHOT_DIR}/10-player-after-game-start.png`, fullPage: true });
  const playerUrl = playerPage.url();
  const playerBodyText = await playerPage.textContent('body');
  console.log('  Player URL:', playerUrl);
  console.log('  Player page text (first 1500 chars):', playerBodyText.substring(0, 1500));

  const isOnPromptPage = /prompt/i.test(playerUrl) || /fill/i.test(playerUrl) || /prompt/i.test(playerBodyText) || /fill in/i.test(playerBodyText) || /noun|verb|adjective|name/i.test(playerBodyText);
  console.log('  Player transitioned to prompting page:', isOnPromptPage);

  if (isOnPromptPage) {
    console.log('\n=== SUCCESS: Player automatically transitioned to prompting page! Bug #2 is FIXED. ===');
  } else {
    const stuckOnLobby = /lobby/i.test(playerUrl) || /waiting/i.test(playerBodyText);
    if (stuckOnLobby) {
      console.log('\n=== FAILURE: Player is STUCK on lobby. Bug #2 is NOT fixed. ===');
    } else {
      console.log('\n=== UNCLEAR: Player is on an unexpected page. Check screenshots. ===');
    }
  }

  await browser.close();
  console.log('\n=== Test complete. Screenshots saved to', SCREENSHOT_DIR, '===');
})();
