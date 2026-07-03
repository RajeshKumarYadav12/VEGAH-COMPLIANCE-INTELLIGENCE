# VEGAH Frontend - Next.js React Application

Modern React frontend for RFP compliance analysis with real-time streaming, compliance matrix visualization, and proposal generation.

## Project Structure

```
frontend/
├── app/                     # Next.js App Router
│   ├── layout.tsx           # Root layout component
│   ├── page.tsx             # Home page (main UI)
│   ├── globals.css          # Global styles
│   └── api/                 # API route handlers (proxy to backend)
│       ├── health/route.ts  # Health check endpoint
│       ├── upload-capabilities/route.ts
│       └── process-rfp/route.ts
├── components/              # React components
│   ├── UploadZone.tsx       # File upload component
│   ├── AgentTimeline.tsx    # Agent execution timeline
│   ├── ComplianceMatrix.tsx # Compliance visualization
│   ├── ProposalViewer.tsx   # Generated proposal viewer
│   └── ModelToggle.tsx      # LLM model selector
├── hooks/                   # Custom React hooks
│   └── useRFPStream.ts      # Server-Sent Events hook
├── lib/                     # Utilities
│   └── api.ts               # API client functions
├── types/                   # TypeScript types
│   └── rfp.ts               # Domain models
├── public/                  # Static assets
├── package.json             # Dependencies
├── tsconfig.json            # TypeScript config
├── next.config.ts           # Next.js config
├── tailwind.config.mjs      # Tailwind CSS config
├── postcss.config.mjs       # PostCSS config
└── README.md                # This file
```

## Setup

### Install Dependencies

```bash
npm install
```

### Environment Configuration

Create a `.env.local` file:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

For production:

```
NEXT_PUBLIC_API_URL=https://your-backend-url.com
```

## Running the App

### Development (with hot reload)

```bash
npm run dev
```

Access at: http://localhost:3000

### Production Build

```bash
npm run build
npm start
```

## Build

### Development Build

```bash
npm run build
```

Generates `.next/` directory with optimized bundle.

### Production Build

```bash
npm run build
npm start
```

## Key Features

### Upload Zone

- Drag-and-drop CSV file upload
- File type validation
- Progress tracking
- Error handling

### RFP Processing

- PDF file selection
- Real-time streaming of analysis
- Agent execution timeline display
- Model selection (Claude, GPT-4, Groq)

### Compliance Matrix

- Interactive table visualization
- Coverage percentage calculation
- Gap analysis highlighting
- Sortable columns

### Proposal Viewer

- Markdown rendering of generated proposal
- Copy to clipboard
- PDF export functionality
- Responsive layout

### API Client

Located in `lib/api.ts`:

- `uploadCapabilities()` - POST capabilities CSV
- `checkHealth()` - GET backend health
- `processRFP()` - POST RFP processing with SSE streaming

## Hooks

### useRFPStream

Custom hook for Server-Sent Events (SSE) streaming:

```typescript
const { response, loading, error, processRFP } = useRFPStream();
```

Handles real-time streaming of RFP analysis results from backend.

## Styling

- **Tailwind CSS 4** - Utility-first CSS framework
- **Dark Mode** - Built-in dark mode support
- **Responsive** - Mobile-first responsive design
- **Custom Components** - Reusable component library

## TypeScript

All components use TypeScript for type safety:

- Type definitions in `types/rfp.ts`
- Strict type checking enabled
- No `any` types allowed

## Linting

```bash
npm run lint
```

Uses ESLint with Next.js configuration.

## Performance

- **SSR** - Server-side rendering for initial page load
- **ISR** - Incremental Static Regeneration where applicable
- **Image Optimization** - Next.js automatic image optimization
- **Code Splitting** - Automatic code splitting per page
- **Tree Shaking** - Unused code removal in production

## Production Deployment

See root [DEPLOYMENT.md](../DEPLOYMENT.md) for Render deployment guide.

### Build & Start

```bash
npm run build
npm start
```

### Docker Deployment

```dockerfile
FROM node:22-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build
CMD ["npm", "start"]
```

## Environment Variables

- `NEXT_PUBLIC_API_URL` - Backend API base URL (required)

## Troubleshooting

### Port 3000 Already in Use

```bash
lsof -i :3000
kill -9 <PID>
```

### API Connection Error

- Verify `NEXT_PUBLIC_API_URL` in `.env.local`
- Check backend is running on the configured port
- Check CORS headers from backend

### Build Failures

```bash
rm -rf .next node_modules
npm install
npm run build
```

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
