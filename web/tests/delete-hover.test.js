import test from 'node:test';
import assert from 'node:assert/strict';
import { bindDeleteHover } from '../js/sections.js';

function cardFixture() {
  const events = {}, classes = new Set();
  const card = {
    addEventListener: (name, callback) => { events[name] = callback; },
    classList: { add: name => classes.add(name), remove: name => classes.delete(name), contains: name => classes.has(name) },
  };
  const timers = new Map();
  bindDeleteHover(card, timers, 'voice-test');
  return { enter: () => events.pointerenter({ pointerType: 'mouse' }), leave: () => events.pointerleave(),
    visible: () => classes.has('delete-visible'), timers };
}

test('delete button remains visible for 500ms after leaving', context => {
  context.mock.timers.enable({ apis: ['setTimeout'] });
  const card = cardFixture();
  card.enter(); context.mock.timers.tick(1000);
  assert.equal(card.visible(), true);
  card.leave(); context.mock.timers.tick(499);
  assert.equal(card.visible(), true);
  context.mock.timers.tick(1);
  assert.equal(card.visible(), false);
  assert.equal(card.timers.size, 0);
});

test('returning before timeout keeps the button visible and cancels hiding', context => {
  context.mock.timers.enable({ apis: ['setTimeout'] });
  const card = cardFixture();
  card.enter(); context.mock.timers.tick(1000);
  card.leave(); context.mock.timers.tick(300); card.enter();
  context.mock.timers.tick(1500);
  assert.equal(card.visible(), true);
  card.leave(); context.mock.timers.tick(500);
  assert.equal(card.visible(), false);
});

test('leaving before the original one-second reveal cancels it', context => {
  context.mock.timers.enable({ apis: ['setTimeout'] });
  const card = cardFixture();
  card.enter(); context.mock.timers.tick(500); card.leave();
  context.mock.timers.tick(1500);
  assert.equal(card.visible(), false);
  assert.equal(card.timers.size, 0);
});
