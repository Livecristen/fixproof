const test = require("node:test");
const assert = require("node:assert");
const { sum } = require("./sum.js");

test("sum of empty list is 0", () => {
  assert.strictEqual(sum([]), 0);
});
