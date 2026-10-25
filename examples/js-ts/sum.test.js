const test = require("node:test");
const assert = require("node:assert");
const { sum } = require("./sum.js");

test("sum adds every element", () => {
  assert.strictEqual(sum([1, 2, 3]), 6);
});
