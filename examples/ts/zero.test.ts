import test from "node:test";
import assert from "node:assert";
import { finalPrice } from "./price.ts";

test("zero discount keeps price", () => {
  assert.strictEqual(finalPrice(50, 0), 50);
});
