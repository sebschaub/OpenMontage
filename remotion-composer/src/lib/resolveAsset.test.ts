import { describe, it, expect } from "vitest";
import { resolveAsset } from "./resolveAsset";

// staticFile stub mirrors Remotion: maps a public-relative path to /public/<path>
const sf = (p: string) => `/public/${p}`;

describe("resolveAsset", () => {
  it("passes http(s)/data URLs through untouched", () => {
    expect(resolveAsset("https://x.com/a.mp4", sf)).toBe("https://x.com/a.mp4");
    expect(resolveAsset("data:image/png;base64,AAAA", sf)).toBe("data:image/png;base64,AAAA");
  });

  it("preserves the leading slash of a Unix file:// URI (the bug)", () => {
    // Must NOT become file:///opt or /public/opt — must stay a valid absolute file URI
    expect(resolveAsset("file:///opt/openmontage/projects/spike-reel/assets/video/s1.mp4", sf))
      .toBe("file:///opt/openmontage/projects/spike-reel/assets/video/s1.mp4");
  });

  it("converts a bare Unix absolute path to a file:// URI", () => {
    expect(resolveAsset("/opt/x/s1.mp4", sf)).toBe("file:///opt/x/s1.mp4");
  });

  it("routes a genuine public-relative path through staticFile", () => {
    expect(resolveAsset("logos/brand.png", sf)).toBe("/public/logos/brand.png");
  });

  it("handles a Windows absolute path", () => {
    expect(resolveAsset("C:/assets/s1.mp4", sf)).toBe("file:///C:/assets/s1.mp4");
  });
});
