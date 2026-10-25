import test from "node:test";
import assert from "node:assert";
import { finalPrice } from "./price.ts";

test("discount is subtracted", () => {
  assert.strictEqual(finalPrice(100, 20), 80);
});
