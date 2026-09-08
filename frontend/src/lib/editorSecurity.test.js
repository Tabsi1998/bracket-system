import { Editor, mergeAttributes } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import { DOMSerializer } from "@tiptap/pm/model";
import frontendPackage from "../../package.json";

test("all Tiptap packages and optional menu pins use the same exact version", () => {
  const version = frontendPackage.dependencies["@tiptap/core"];
  expect(version).toMatch(/^\d+\.\d+\.\d+$/);
  for (const [name, dependencyVersion] of Object.entries(frontendPackage.dependencies)) {
    if (name.startsWith("@tiptap/")) expect(dependencyVersion, name).toBe(version);
  }
  for (const name of ["@tiptap/extension-bubble-menu", "@tiptap/extension-floating-menu"]) {
    expect(frontendPackage.resolutions[name], name).toBe(version);
  }
});

test("JSON-origin prototype keys cannot become inherited DOM attributes", () => {
  const input = JSON.parse(
    '{"__proto__":{"data-inherited-canary":"present","src":"invalid:canary","onerror":"void 0"}}',
  );
  const attrs = mergeAttributes({ alt: "Safe image" }, input);

  expect(Object.getPrototypeOf(attrs)).toBe(Object.prototype);
  expect(attrs["data-inherited-canary"]).toBeUndefined();
  expect(attrs.onerror).toBeUndefined();
  // The upstream fix preserves the key as an inert own data property.
  expect(Object.getOwnPropertyDescriptor(attrs, "__proto__").value).toBe(input.__proto__);

  const { dom } = DOMSerializer.renderSpec(document, ["img", attrs]);
  expect(dom.getAttribute("alt")).toBe("Safe image");
  for (const name of ["data-inherited-canary", "src", "onerror"]) {
    expect(dom.hasAttribute(name)).toBe(false);
  }
});

test("the patched editor still edits and serializes formatted content", () => {
  const editor = new Editor({
    extensions: [StarterKit],
    content: "<p>Hello <strong>Lions</strong></p>",
  });
  try {
    expect(editor.getHTML()).toBe("<p>Hello <strong>Lions</strong></p>");
    editor.commands.setContent("<p>Updated <em>content</em></p>");
    expect(editor.getJSON().content[0].content[1].marks).toEqual([{ type: "italic" }]);
    expect(editor.getHTML()).toBe("<p>Updated <em>content</em></p>");
  } finally {
    editor.destroy();
  }
});
