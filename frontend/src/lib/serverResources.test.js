import { safeResourceUrl } from "./serverResources";

test.each(["javascript:alert(1)", "data:text/html,test", "http://example.test/mod", "//example.test/mod", "https://user:secret@example.test/mod", "https://example.test/\nmod", "https://example.test\\@evil.test", "", null])("unsafe mod link is not rendered: %s", (url) => {
  expect(safeResourceUrl(url)).toBe("");
});

test("HTTPS download URLs retain their version and fragment", () => {
  expect(safeResourceUrl("https://example.test/mod.zip?v=2#install")).toBe("https://example.test/mod.zip?v=2#install");
});
