# Pragmatic File Declutter — Knowledge Base

> **Nota para futuras sessões Claude:** Este arquivo é a fonte de verdade do projeto.
> Itens marcados com [PRECO] e [TENDENCIA] devem ser revalidados a cada 3 meses.
> Última atualização: 2026-02-16

---

## 1. Hardware do Usuário

- [FATO] 16GB RAM DDR4
- [FATO] NVIDIA GeForce RTX 3050 (CUDA capable, ~4GB VRAM)
- [FATO] Windows 11
- [FATO] Git 2.53.0 instalado
- [FATO] GitHub CLI 2.86.0 instalado, autenticado como `fabiomobil`
- [FATO] Volume inicial: ~10.000 fotos
- [FATO] Volume mensal: centenas de fotos novas
- [FATO] Usuário tem iPhone (fotos HEIC) e fotografa em RAW

**Implicações:**
- RTX 3050 suporta CUDA → CLIP roda localmente com boa performance
- 16GB RAM → pode processar batches de ~500 imagens por vez
- VRAM 4GB → CLIP ViT-B/32 cabe (~400MB), modelos maiores não

---

## 2. Deduplicação

### Abordagem escolhida
- [ESCOLHA] Perceptual hashing com `imagehash` library
- [ESCOLHA] Dois algoritmos combinados: pHash (DCT-based) + dHash (gradient-based)
- [ESCOLHA] Hamming distance thresholds:
  - 0-5: **Idênticas** → pasta `duplicadas/identicas/`
  - 6-10: **Similares** → pasta `duplicadas/similares/`
  - >10: Diferentes, ignorar

### Fluxo
1. Scan todas as imagens → calcular hash de cada
2. Comparar pares (otimizado com BK-tree para evitar O(n²))
3. Agrupar duplicatas
4. Mostrar ao usuário para review (side-by-side comparison)
5. Usuário confirma → move para `apagar/`

### Trade-offs
- pHash sozinho tem falsos positivos com imagens muito simples (céu azul, parede branca)
- dHash complementa com informação de gradiente
- Threshold 5 é conservador (poucos falsos positivos, pode perder algumas duplicatas com crop)
- BK-tree reduz comparações de O(n²) para ~O(n log n)

### Alternativas descartadas
- MD5/SHA256: só detecta cópias bit-a-bit exatas, não pega redimensionamentos
- SSIM: muito lento para 10k+ imagens (requer decodificar toda imagem)
- CNN embeddings: overkill para dedup, reservado para classificação

---

## 3. Classificação

### Pipeline (em ordem)
1. **Heurísticas rápidas** (gratuito, <1ms/foto)
   - Aspect ratio 16:9 ou 9:16 + resolução de tela conhecida → screenshot
   - DPI = 300 + aspect ratio A4/Letter → documento escaneado
   - EXIF com app "Scanner" ou "CamScanner" → documento
   - Nome do arquivo contém "IMG_", "Screenshot_", "receipt" → pista

2. **CLIP local** (gratuito, ~50ms/foto na RTX 3050)
   - [ESCOLHA] Modelo: ViT-B/32 via open-clip-torch
   - Zero-shot classification com prompts:
     - "a screenshot of a computer or phone screen"
     - "a photo of a paper document or receipt"
     - "a receipt from a store or restaurant"
     - "a random personal photograph"
   - Cosine similarity → categoria com maior score

3. **Gemini 2.0 Flash API** (pago, ~100ms/foto)
   - [ESCOLHA] Apenas para fotos com confidence CLIP < 50%
   - Prompt estruturado pedindo classificação + confidence
   - [PRECO] ~$0.001/foto (input: $0.10/1M tokens, output: $0.40/1M tokens)
   - [PRECO] Free tier: 15 RPM, 1M tokens/min, 1500 req/dia

4. **GPT-4o mini fallback** (pago, ~150ms/foto)
   - [ESCOLHA] Apenas se Gemini falhar (rate limit, erro, downtime)
   - [PRECO] ~$0.002/foto (input: $0.15/1M tokens, output: $0.60/1M tokens)

### Categorias
- `screenshots/` — Capturas de tela (desktop, mobile)
- `documents/` — Documentos escaneados, PDFs fotografados, whiteboards
- `receipts/` — Notas fiscais, recibos, comprovantes
- `random/` — Catch-all para fotos que não se encaixam

### Confidence scoring
- [ESCOLHA] High (>85%): auto-move, mostrar no resultado
- [ESCOLHA] Medium (50-85%): fila de review humano
- [ESCOLHA] Low (<50%): mover para `random/`

---

## 4. APIs e Pricing

### Gemini 2.0 Flash (Primary)
- [PRECO] Input: $0.10/1M tokens | Output: $0.40/1M tokens
- [PRECO] Free tier: 15 RPM, 1M tokens/min, 1500 req/dia
- [FATO] Suporta imagens até 20MB
- [FATO] Contexto: 1M tokens
- [ESCOLHA] API primária por ser mais barata e ter free tier generoso

### GPT-4o mini (Fallback)
- [PRECO] Input: $0.15/1M tokens | Output: $0.60/1M tokens
- [FATO] Contexto: 128k tokens
- [ESCOLHA] Fallback para quando Gemini falha

### Estimativa de custo para 10.000 fotos
- ~90% processadas localmente (CLIP) = 9.000 fotos grátis
- ~10% enviadas para API = 1.000 fotos
- Custo Gemini: ~$1.00
- Custo GPT (se usado): ~$2.00
- **Total estimado: $1.00 - $1.10** (cenário misto)

### UX de custos
- [ESCOLHA] Sempre mostrar estimativa ANTES de chamar APIs
- [ESCOLHA] Mostrar quotes de Gemini e GPT lado a lado
- [ESCOLHA] Usuário escolhe qual usar ou cancela

---

## 5. Clustering por Evento

### Abordagem: Temporal-First
- [ESCOLHA] Temporal primeiro, visual depois (mais eficiente)
- Razão: Ordenar por data é O(n log n), clustering visual é O(n²)

### Fluxo
1. Ordenar fotos por data EXIF
2. Gap > 48 horas entre fotos consecutivas = novo cluster temporal
3. Dentro de cada cluster temporal, extrair embeddings CLIP
4. HDBSCAN para sub-dividir clusters grandes (>50 fotos) em sub-eventos visuais
5. Sugerir nome do evento baseado em:
   - Localização GPS (se disponível via EXIF)
   - Conteúdo visual (CLIP → texto descritivo)
   - Data range

### HDBSCAN
- [ESCOLHA] HDBSCAN ao invés de K-Means (não precisa especificar K)
- `min_cluster_size=5` como default
- Permite outliers (fotos que não pertencem a nenhum evento → `random/`)

### Nomeação de eventos
- [ESCOLHA] Formato: `YYYY-MM-DD_Nome-do-Evento`
- Sugestão automática + edição pelo usuário
- Rename batch das fotos dentro do evento (opcional)

---

## 6. UI — NiceGUI

### Framework
- [ESCOLHA] NiceGUI com `native=True` (usa pywebview por baixo)
- Parece app desktop nativo, não browser
- Suporta Tailwind CSS built-in
- Hot reload em dev

### Páginas planejadas
1. **Select Folder** — Escolher pasta raiz + scan
2. **Overview/Dashboard** — Resumo após scan (total fotos, estimativas, custo API)
3. **Dedup Review** — Comparação side-by-side de duplicatas
4. **Classify** — Grid com categorias e confidence badges
5. **Events** — Timeline visual de eventos detectados
6. **Rename** — Batch rename dentro de eventos
7. **Search** — CLIP text→image search (futuro)
8. **Report** — Resumo final do que foi feito

### Componentes
- Photo grid (lazy loading)
- Side-by-side comparison (dedup)
- Progress bar com ETA
- Confidence badge (green/yellow/red)
- Timeline chart
- Filter bar
- Undo bar (persistent bottom bar)
- Drag & drop entre categorias

---

## 7. File Safety

### Regra absoluta
- [ESCOLHA] **NUNCA deletar arquivos** — apenas `shutil.move()`
- [ESCOLHA] **NUNCA copiar** — apenas mover (evitar duplicação de espaço)
- [ESCOLHA] Todo move é logado em undo stack (JSON)
- [ESCOLHA] Undo disponível para qualquer operação

### Implementação
```python
# ÚNICO método permitido para mover arquivos
def safe_move(src: Path, dst: Path, undo_stack: UndoStack) -> None:
    assert src.exists(), f"Source not found: {src}"
    assert not dst.exists(), f"Destination exists: {dst}"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    undo_stack.push(MoveRecord(src=src, dst=dst, timestamp=datetime.now()))
```

### Undo stack
- JSON file em `_pragmatic_declutter/_undo_history.json`
- Cada entry: `{src, dst, timestamp, operation_type}`
- Undo reverte o move (dst → src)
- Stack persiste entre sessões

---

## 8. Versioning

- [ESCOLHA] SemVer (MAJOR.MINOR.PATCH)
- [ESCOLHA] Commitizen para auto-bump e changelog
- [ESCOLHA] Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`)
- Single source of version: `pyproject.toml` → `[project] version`
- Commitizen lê de lá e bumpa automaticamente

### Regras de bump
- `feat:` → MINOR bump
- `fix:` → PATCH bump
- `BREAKING CHANGE:` → MAJOR bump
- Antes de v1.0.0: qualquer breaking change é MINOR

---

## 9. CI/CD — GitHub Actions

### Workflows
1. **ci.yml** — Em todo push e PR
   - Ruff lint + format check
   - Mypy type check
   - Pytest com coverage report
   - Roda em ubuntu-latest + windows-latest

2. **release.yml** — Em merge para main com tag
   - Commitizen bump version
   - Gerar CHANGELOG
   - Criar GitHub Release

3. **build.yml** — Manual ou em release
   - Nuitka compile para Windows .exe
   - Upload como release asset

### Pre-commit hooks (local)
- ruff (lint + format)
- mypy (type check)
- commitizen (validar commit message)

---

## 10. Claude Code Infrastructure

### Agents (.claude/agents/)
- [ESCOLHA] Subagents (não Agent Teams — são experimentais e 15x mais caros em tokens)
- 7 agents especializados:
  - `pm.md` — Product Manager
  - `architect.md` — System Architect
  - `backend.md` — Backend Developer
  - `frontend.md` — Frontend Developer
  - `tester.md` — QA Engineer
  - `debugger.md` — Debugger
  - `reviewer.md` — Code Reviewer

### Custom Commands (.claude/commands/)
- `test.md` — Rodar suite de testes
- `review.md` — Code review de mudanças
- `build.md` — Build local

### Skills (.claude/skills/)
- `photo-processing.md` — Como processar diferentes formatos
- `file-safety.md` — Regras de file safety
- `api-cost.md` — Pricing e estimativas de custo

### Settings
- `.claude/settings.json` com configurações do projeto

---

## 11. Dependencies

### Core
```
nicegui>=2.0,<3.0           # UI framework
pywebview>=5.0,<6.0         # Native window
Pillow>=10.0,<11.0          # Image processing
pillow-heif>=0.18,<1.0      # HEIC support
rawpy>=0.21,<1.0            # RAW format support
imagehash>=4.3,<5.0         # Perceptual hashing
open-clip-torch>=2.24,<3.0  # CLIP model
torch>=2.0                  # PyTorch (CUDA)
torchvision>=0.15           # Image transforms
hdbscan>=0.8,<1.0           # Clustering
scikit-learn>=1.3,<2.0      # ML utilities
google-generativeai>=0.8    # Gemini API
openai>=1.0,<2.0            # GPT API
tufup>=1.0,<2.0             # Auto-update
exifread>=3.0,<4.0          # EXIF metadata
```

### Dev
```
pytest>=8.0,<9.0
pytest-cov>=5.0,<6.0
pytest-asyncio>=0.23
ruff>=0.8,<1.0
mypy>=1.8,<2.0
commitizen>=3.0,<4.0
pre-commit>=3.0,<4.0
```

### Build
```
nuitka>=2.0,<3.0
ordered-set>=4.0
```

---

## 12. Formatos Suportados

### Imagens
- [FATO] JPEG (.jpg, .jpeg) — Pillow nativo
- [FATO] PNG (.png) — Pillow nativo
- [FATO] WebP (.webp) — Pillow nativo
- [FATO] HEIC (.heic, .heif) — via pillow-heif (usuário tem iPhone)
- [FATO] RAW (.cr2, .cr3, .nef, .arw, .dng, .orf, .rw2) — via rawpy (usuário fotografa em RAW)
- [FATO] TIFF (.tiff, .tif) — Pillow nativo
- [FATO] BMP (.bmp) — Pillow nativo
- [FATO] GIF (.gif) — Pillow nativo (só primeiro frame)

### Vídeos
- [ESCOLHA] Não processar, apenas mover para pasta `videos/`
- Extensões detectadas: .mp4, .mov, .avi, .mkv, .wmv, .flv, .webm, .m4v, .3gp

### Outros
- [ESCOLHA] Arquivos não reconhecidos ficam no lugar original (não toca)

---

## 13. Output Folder Structure

```
[pasta_escolhida_pelo_usuario]/_pragmatic_declutter/
├── duplicadas/
│   ├── identicas/     # Duplicatas exatas (hamming 0-5)
│   ├── similares/     # Fotos similares (hamming 6-10)
│   └── apagar/        # Confirmadas pelo usuário para deletar
├── misc/
│   ├── screenshots/   # Capturas de tela
│   ├── documents/     # Documentos escaneados
│   ├── receipts/      # Recibos e notas fiscais
│   └── random/        # Não classificadas / baixa confiança
├── organize/
│   └── [YYYY-MM-DD_Event-Name]/  # Eventos detectados
├── videos/            # Vídeos movidos sem processamento
├── corrupted/         # Arquivos corrompidos
├── no_metadata/       # Sem EXIF/metadata
└── _reports/          # Relatórios de execução
    └── _undo_history.json
```

---

## 14. Product Vision & Roadmap

### Visão
Pragmatic File Declutter — ferramenta pragmática para declutter digital.
Começamos com fotos, expandimos para arquivos gerais, depois backups e cloud.

### Roadmap
| Versão | Nome | Escopo |
|--------|------|--------|
| v0.1.0 | Scan + Dedup | Scanner de pastas + deduplicação por hash |
| v0.2.0 | Classify | Classificação em misc categories |
| v0.3.0 | Events | Clustering temporal + visual por evento |
| v0.4.0 | Search | Busca CLIP text→image |
| v1.0.0 | Photo Declutter | Release estável com polish |
| v2.0.0 | File Declutter | Expandir para arquivos gerais |
| v3.0.0 | Mobile Connect | Android backup declutter |
| v4.0.0 | Cloud Sync | Google Photos, iCloud integration |

### Arquitetura plugável
- `core/` contém lógica de negócio pura
- `services/` abstrai fontes de dados (filesystem, Android, cloud)
- `ui/` é intercambiável (desktop agora, possível mobile/web futuro)

---

## 15. Decisões Pendentes

- [ ] Threshold exato de HDBSCAN `min_cluster_size` (testar com dados reais)
- [ ] Formato exato do relatório de execução
- [ ] Ícone/logo do app
- [ ] Tema de cores da UI
- [ ] Se suportará múltiplos idiomas na UI (pt-BR e en por ora)

---

## 16. Referências

- [imagehash docs](https://github.com/JohannesBuchner/imagehash)
- [open-clip-torch](https://github.com/mlfoundations/open_clip)
- [NiceGUI docs](https://nicegui.io/documentation)
- [HDBSCAN docs](https://hdbscan.readthedocs.io/)
- [Commitizen docs](https://commitizen-tools.github.io/commitizen/)
- [Nuitka docs](https://nuitka.net/doc/user-manual.html)
- [tufup docs](https://github.com/dfdx/tufup)
- [Gemini API pricing](https://ai.google.dev/pricing)
- [OpenAI API pricing](https://openai.com/api/pricing/)

---

## 17. GitHub

- [FATO] Repo: `fabiomobil/pragmatic-file-declutter`
- [FATO] Visibilidade: público
- [FATO] User: fabiomobil
- [FATO] Path local: `C:\Users\Moriya\Dev\pragmatic-file-declutter`
- [ESCOLHA] Branch strategy: GitHub Flow (main + feature branches)
- [ESCOLHA] License: MIT

---

## 18. Histórico de Decisões

| Data | Decisão | Contexto |
|------|---------|----------|
| 2026-02-16 | Nome: Pragmatic File Declutter | Após testar Sift, Trimly, Decluttr — todos ocupados. Nome descritivo, sem conflito. |
| 2026-02-16 | NiceGUI com native=True | Parece desktop nativo, hot reload, Tailwind built-in |
| 2026-02-16 | Gemini 2.0 Flash como API primária | Mais barato que GPT, free tier generoso |
| 2026-02-16 | Temporal-first clustering | O(n log n) vs O(n²) visual-first. Exemplo: praia em Cancún e Floripa são visualmente similares mas eventos diferentes |
| 2026-02-16 | Subagents ao invés de Agent Teams | Agent Teams são experimentais e 15x mais caros em tokens |
| 2026-02-16 | Nuitka ao invés de PyInstaller | Compila Python→C, melhor performance, anti-virus não bloqueia |
| 2026-02-16 | Projeto fora do OneDrive | OneDrive causa file locking, sync issues, corrupção .git |
| 2026-02-16 | HEIC + RAW suportados | Usuário tem iPhone (HEIC) e fotografa em RAW |
| 2026-02-16 | Vídeos: mover sem processar | Move para pasta videos/, não analisa conteúdo |
