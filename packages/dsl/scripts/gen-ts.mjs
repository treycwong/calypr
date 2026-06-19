// Generate TypeScript types from the committed JSON Schema (Pydantic is the source of
// truth). Paths are resolved relative to this file so it runs from any cwd.
import { compileFromFile } from "json-schema-to-typescript";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const pkgRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const input = join(pkgRoot, "ts/schema/graphspec.schema.json");
const output = join(pkgRoot, "ts/generated/graphspec.ts");

const ts = await compileFromFile(input, {
  bannerComment:
    "/* AUTO-GENERATED from packages/dsl (Pydantic). DO NOT EDIT — run `pnpm --filter @calypr/dsl gen`. */",
  additionalProperties: false,
  style: { singleQuote: false },
});

mkdirSync(dirname(output), { recursive: true });
writeFileSync(output, ts);
console.log(`wrote ${output}`);
