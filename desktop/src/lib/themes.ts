import type { ThemeKey } from "./ipc";

export interface ThemeMeta {
  key: ThemeKey;
  label: string;
  accent: string;
  swatches: [string, string, string, string, string];
}

export const THEMES: ThemeMeta[] = [
  {
    key: "forest",
    label: "Forest",
    accent: "#5ee28d",
    swatches: ["#222b26", "#254f32", "#267443", "#35a95d", "#5ee28d"],
  },
  {
    key: "ocean",
    label: "Ocean",
    accent: "#55c7f5",
    swatches: ["#202d38", "#1c4960", "#176b8e", "#2398c5", "#55c7f5"],
  },
  {
    key: "violet",
    label: "Violet",
    accent: "#b98cff",
    swatches: ["#2a2532", "#453269", "#65449a", "#8a5bd0", "#b98cff"],
  },
  {
    key: "ember",
    label: "Ember",
    accent: "#ff9a62",
    swatches: ["#30251f", "#613424", "#91472a", "#c86138", "#ff9a62"],
  },
  {
    key: "mono",
    label: "Mono",
    accent: "#eeeeee",
    swatches: ["#292929", "#4c4c4c", "#747474", "#aaaaaa", "#eeeeee"],
  },
  {
    key: "paper",
    label: "Paper",
    accent: "#2f6b4f",
    swatches: ["#ece6d9", "#cfdcd1", "#9fbfa9", "#5f9473", "#2f6b4f"],
  },
];

export const themeMeta = (key: ThemeKey): ThemeMeta =>
  THEMES.find((theme) => theme.key === key) ?? THEMES[0];
