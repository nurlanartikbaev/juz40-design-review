// Собирает доску дизайн-ревью. Передай этот код в use_figma, заменив DATA.
// mode "init" создаёт страницу и сводку. mode "screen" добавляет экран с карточками.
// Для "screen" укажи pageId и rootId из ответа "init".
const DATA = {
  mode: "init",
  pageName: "Дизайн-ревью · Фича · 2026-01-01",
  pageId: null,
  rootId: null,
  summary: {
    feature: "Фича",
    date: "2026-01-01",
    designUrl: "https://www.figma.com/design/KEY/File?node-id=1-2",
    devUrl: "https://stage.example.com/page",
    counts: { critical: 0, major: 0, minor: 0 },
    unchecked: [],
  },
  screen: {
    name: "Экран",
    viewport: "1440 px",
    designUrl: "",
    devUrl: "",
    cards: [
      {
        id: "D-01",
        severity: "major",
        title: "Кнопка меньше на 8 px",
        rows: [{ property: "Высота", design: "48 px", dev: "40 px" }],
        note: "",
        design: { width: 320, height: 120, highlight: { x: 32, y: 32, w: 256, h: 48 } },
        dev: { width: 320, height: 112, highlight: { x: 32, y: 32, w: 256, h: 40 } },
      },
    ],
  },
};

const ROOT_WIDTH = 1760;
const ROOT_PADDING = 64;
const CARD_PADDING = 24;
const COLUMN_GAP = 24;
const CONTENT_WIDTH = ROOT_WIDTH - ROOT_PADDING * 2;
const CARD_INNER = CONTENT_WIDTH - CARD_PADDING * 2;
const COLUMN_WIDTH = (CARD_INNER - COLUMN_GAP) / 2;
const WELL_PADDING = 16;
const MAX_IMAGE_HEIGHT = 520;
const MAX_UPSCALE = 2;

const SEVERITY = {
  critical: { label: "Критично", color: "#C5221F", bg: "#FCE8E6" },
  major: { label: "Важно", color: "#B06000", bg: "#FEF3E0" },
  minor: { label: "Мелочь", color: "#3C4043", bg: "#E8EAED" },
};
const COLORS = {
  page: "#F1F3F4", surface: "#FFFFFF", well: "#F1F3F4", line: "#DADCE0",
  ink: "#202124", muted: "#5F6368", link: "#1A73E8", highlight: "#EA4335", empty: "#DADCE0",
};

const rgb = (hex) => ({
  r: parseInt(hex.slice(1, 3), 16) / 255,
  g: parseInt(hex.slice(3, 5), 16) / 255,
  b: parseInt(hex.slice(5, 7), 16) / 255,
});
const solid = (hex) => [{ type: "SOLID", color: rgb(hex) }];

await figma.loadFontAsync({ family: "Inter", style: "Regular" });
await figma.loadFontAsync({ family: "Inter", style: "Semi Bold" });

function text(characters, options = {}) {
  const { size = 14, bold = false, color = COLORS.ink, width = null, url = null } = options;
  const node = figma.createText();
  node.fontName = { family: "Inter", style: bold ? "Semi Bold" : "Regular" };
  node.fontSize = size;
  node.characters = String(characters);
  node.fills = solid(url ? COLORS.link : color);
  if (width) {
    node.resize(width, node.height);
    node.textAutoResize = "HEIGHT";
  }
  if (url) {
    node.hyperlink = { type: "URL", value: url };
    node.textDecoration = "UNDERLINE";
  }
  return node;
}

function stack(direction, name, gap = 0, padding = 0) {
  const frame = figma.createAutoLayout(direction, { name, itemSpacing: gap });
  frame.paddingTop = frame.paddingBottom = frame.paddingLeft = frame.paddingRight = padding;
  frame.fills = [];
  return frame;
}

function badge(severity) {
  const style = SEVERITY[severity] || SEVERITY.minor;
  const pill = stack("HORIZONTAL", "Критичность");
  pill.paddingTop = pill.paddingBottom = 4;
  pill.paddingLeft = pill.paddingRight = 10;
  pill.cornerRadius = 999;
  pill.fills = solid(style.bg);
  pill.appendChild(text(style.label, { size: 13, bold: true, color: style.color }));
  return pill;
}

function links(designUrl, devUrl) {
  const row = stack("HORIZONTAL", "Ссылки", 16);
  if (designUrl) row.appendChild(text("Открыть макет", { size: 13, url: designUrl }));
  if (devUrl) row.appendChild(text("Открыть дев", { size: 13, url: devUrl }));
  return row;
}

function imageScale(image) {
  const available = COLUMN_WIDTH - WELL_PADDING * 2;
  return Math.min(available / image.width, MAX_IMAGE_HEIGHT / image.height, MAX_UPSCALE);
}

function imageColumn(card, side, label, wellHeight, placeholders) {
  const image = card[side];
  const column = stack("VERTICAL", label, 8);
  column.appendChild(text(label, { size: 13, bold: true, color: COLORS.muted }));

  const well = figma.createFrame();
  well.name = "Скрин";
  well.fills = solid(COLORS.well);
  well.cornerRadius = 8;
  well.layoutMode = "VERTICAL";
  well.primaryAxisAlignItems = "CENTER";
  well.counterAxisAlignItems = "CENTER";
  well.primaryAxisSizingMode = "FIXED";
  well.counterAxisSizingMode = "FIXED";
  well.resize(COLUMN_WIDTH, wellHeight);
  column.appendChild(well);

  if (!image) {
    well.appendChild(text("Элемента нет", { size: 14, color: COLORS.muted }));
    return column;
  }

  const scale = imageScale(image);
  const width = Math.max(1, Math.round(image.width * scale));
  const height = Math.max(1, Math.round(image.height * scale));
  const stage = figma.createFrame();
  stage.name = `${card.id} ${label}`;
  stage.resize(width, height);
  stage.fills = [];
  stage.clipsContent = true;
  well.appendChild(stage);

  const shot = figma.createRectangle();
  shot.name = `img:${card.id}:${side}`;
  shot.resize(width, height);
  shot.fills = solid(COLORS.empty);
  stage.appendChild(shot);
  placeholders.push({ id: shot.id, name: shot.name });

  if (image.highlight) {
    const h = image.highlight;
    const outline = 4;
    const x = Math.max(0, h.x * scale - outline);
    const y = Math.max(0, h.y * scale - outline);
    const frameWidth = Math.min(width - x, h.w * scale + outline * 2);
    const frameHeight = Math.min(height - y, h.h * scale + outline * 2);
    const box = figma.createRectangle();
    box.name = "Рамка";
    box.resize(Math.max(1, frameWidth), Math.max(1, frameHeight));
    box.x = x;
    box.y = y;
    box.fills = [];
    box.strokes = solid(COLORS.highlight);
    box.strokeWeight = 2;
    box.strokeAlign = "INSIDE";
    box.cornerRadius = 4;
    stage.appendChild(box);
  }
  return column;
}

function valuesTable(rows) {
  const table = stack("VERTICAL", "Значения");
  const widths = [CARD_INNER * 0.28, CARD_INNER * 0.36, CARD_INNER * 0.36];
  const addRow = (cells, header) => {
    const row = stack("HORIZONTAL", header ? "Заголовок" : "Строка");
    row.paddingTop = row.paddingBottom = 8;
    row.strokes = solid(COLORS.line);
    row.strokeBottomWeight = 1;
    row.strokeTopWeight = row.strokeLeftWeight = row.strokeRightWeight = 0;
    cells.forEach((cell, index) => {
      row.appendChild(
        text(cell, {
          size: 13,
          bold: header,
          color: header ? COLORS.muted : COLORS.ink,
          width: Math.floor(widths[index]) - 12,
        })
      );
    });
    table.appendChild(row);
  };
  addRow(["Свойство", "Макет", "Дев"], true);
  rows.forEach((r) => addRow([r.property, r.design, r.dev], false));
  return table;
}

function buildCard(card, screen, placeholders) {
  const frame = stack("VERTICAL", `${card.id} ${card.title}`, 20, CARD_PADDING);
  frame.fills = solid(COLORS.surface);
  frame.cornerRadius = 12;

  const header = stack("HORIZONTAL", "Заголовок", 12);
  header.counterAxisAlignItems = "CENTER";
  header.appendChild(text(card.id, { size: 14, bold: true, color: COLORS.muted }));
  header.appendChild(badge(card.severity));
  header.appendChild(text(card.title, { size: 20, bold: true }));
  frame.appendChild(header);

  const heights = [card.design, card.dev].filter(Boolean).map((i) => i.height * imageScale(i));
  const wellHeight = Math.ceil(Math.max(120, ...heights)) + WELL_PADDING * 2;
  const images = stack("HORIZONTAL", "Скрины", COLUMN_GAP);
  images.appendChild(imageColumn(card, "design", "Макет", wellHeight, placeholders));
  images.appendChild(imageColumn(card, "dev", "Дев", wellHeight, placeholders));
  frame.appendChild(images);

  if (card.rows && card.rows.length) frame.appendChild(valuesTable(card.rows));
  if (card.note) frame.appendChild(text(card.note, { size: 13, color: COLORS.muted, width: CARD_INNER }));
  frame.appendChild(links(card.designUrl || screen.designUrl, card.devUrl || screen.devUrl));
  return frame;
}

function buildSummary(summary) {
  const frame = stack("VERTICAL", "Сводка", 20, 32);
  frame.fills = solid(COLORS.surface);
  frame.cornerRadius = 12;
  frame.appendChild(text(`Дизайн-ревью: ${summary.feature}`, { size: 32, bold: true }));
  frame.appendChild(text(summary.date, { size: 14, color: COLORS.muted }));

  const counts = stack("HORIZONTAL", "Итоги", 12);
  for (const key of ["critical", "major", "minor"]) {
    const style = SEVERITY[key];
    const item = stack("HORIZONTAL", style.label, 8);
    item.paddingTop = item.paddingBottom = 8;
    item.paddingLeft = item.paddingRight = 14;
    item.cornerRadius = 8;
    item.fills = solid(style.bg);
    item.appendChild(text(style.label, { size: 14, color: style.color }));
    item.appendChild(text(summary.counts[key] || 0, { size: 14, bold: true, color: style.color }));
    counts.appendChild(item);
  }
  frame.appendChild(counts);
  frame.appendChild(links(summary.designUrl, summary.devUrl));

  if (summary.unchecked && summary.unchecked.length) {
    const list = stack("VERTICAL", "Не проверено", 6);
    list.appendChild(text("Не проверено", { size: 16, bold: true }));
    const width = CONTENT_WIDTH - 64;
    summary.unchecked.forEach((item) => list.appendChild(text(item, { size: 14, width })));
    frame.appendChild(list);
  }
  return frame;
}

function uniquePageName(name) {
  const used = new Set(figma.root.children.map((p) => p.name));
  if (!used.has(name)) return name;
  let index = 2;
  while (used.has(`${name} (${index})`)) index += 1;
  return `${name} (${index})`;
}

if (DATA.mode === "init") {
  const firstPage = figma.root.children[0];
  const page = figma.createPage();
  try {
    page.name = uniquePageName(DATA.pageName);
    await figma.setCurrentPageAsync(page);
    const root = stack("VERTICAL", "Дизайн-ревью", 48, ROOT_PADDING);
    root.fills = solid(COLORS.page);
    root.x = 100;
    root.y = 100;
    page.appendChild(root);
    root.counterAxisSizingMode = "FIXED";
    root.resize(ROOT_WIDTH, root.height);
    root.primaryAxisSizingMode = "AUTO";
    const summary = buildSummary(DATA.summary);
    root.appendChild(summary);
    summary.layoutSizingHorizontal = "FILL";
    return { pageId: page.id, pageName: page.name, rootId: root.id, createdNodeIds: [page.id, root.id, summary.id] };
  } catch (error) {
    await figma.setCurrentPageAsync(firstPage);
    page.remove();
    throw error;
  }
}

if (DATA.mode === "screen") {
  const page = await figma.getNodeByIdAsync(DATA.pageId);
  if (!page || page.type !== "PAGE") throw new Error("Страница ревью не найдена");
  await figma.setCurrentPageAsync(page);
  const root = await figma.getNodeByIdAsync(DATA.rootId);
  if (!root || root.type !== "FRAME") throw new Error("Доска ревью не найдена");

  const screen = DATA.screen;
  const sectionName = `Экран: ${screen.name} · ${screen.viewport}`;
  // Повторный запуск заменяет только секцию этого экрана на доске ревью.
  root.children.filter((n) => n.name === sectionName).forEach((n) => n.remove());

  const section = stack("VERTICAL", sectionName, 24);
  root.appendChild(section);
  section.layoutSizingHorizontal = "FILL";
  const heading = stack("HORIZONTAL", "Заголовок экрана", 12);
  heading.counterAxisAlignItems = "BASELINE";
  heading.appendChild(text(screen.name, { size: 24, bold: true }));
  heading.appendChild(text(screen.viewport, { size: 14, color: COLORS.muted }));
  section.appendChild(heading);

  const placeholders = [];
  const cardIds = [];
  for (const card of screen.cards) {
    const node = buildCard(card, screen, placeholders);
    section.appendChild(node);
    node.layoutSizingHorizontal = "FILL";
    cardIds.push(node.id);
  }
  return { sectionId: section.id, cardIds, placeholders, nodeIds: placeholders.map((p) => p.id) };
}

throw new Error('DATA.mode должен быть "init" или "screen"');
