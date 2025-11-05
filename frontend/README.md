# DICOM Gateway Frontend

Vue.js 3 frontend for the DICOM Gateway management interface.

## Development

### Prerequisites

- Node.js 20.x LTS or higher
- npm 10.x or higher

### Installation

```bash
# Install dependencies
npm install

# Development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Lint code
npm run lint
```

## Dependencies

### Production Dependencies

- **Vue 3.5+** - Progressive JavaScript framework
- **Vue Router 4.4+** - Official router for Vue.js
- **Pinia 2.2+** - State management for Vue
- **Axios 1.7+** - HTTP client
- **@headlessui/vue** - Unstyled UI components
- **@heroicons/vue** - Icon library
- **Chart.js 4.4+** - Charting library
- **vue-chartjs** - Vue wrapper for Chart.js
- **date-fns 4.1+** - Date utility library

### Development Dependencies

- **Vite 5.4+** - Next generation frontend tooling
- **Tailwind CSS 3.4+** - Utility-first CSS framework
- **ESLint 8.57+** - Code linting
- **eslint-plugin-vue** - Vue.js specific ESLint rules

## Deprecation Warnings

When running `npm install`, you may see deprecation warnings for packages like:
- `inflight`, `glob@7`, `rimraf@3` - These are transitive dependencies (dependencies of dependencies)
- `@humanwhocodes/*` packages - Used by ESLint 8, will be resolved when ESLint 9 is adopted

These warnings are **safe to ignore** for now. They come from older transitive dependencies that will be updated when their parent packages release new versions. The build and runtime functionality are not affected.

To minimize warnings:
1. Keep dependencies updated (run `npm update` periodically)
2. Consider upgrading to ESLint 9 when ready (requires configuration changes)

## Building for Production

The frontend is built as static files that are served by Nginx:

```bash
npm run build
```

Output is in `frontend/dist/` directory, which is configured to be served by Nginx in the RPM installation.

## Project Structure

```
frontend/
├── src/
│   ├── api/          # API client and services
│   ├── components/   # Vue components
│   ├── router/       # Vue Router configuration
│   ├── stores/       # Pinia stores
│   ├── views/        # Page components
│   ├── App.vue       # Root component
│   ├── main.js       # Application entry point
│   └── style.css     # Global styles
├── index.html        # HTML template
├── vite.config.js    # Vite configuration
├── tailwind.config.js # Tailwind CSS configuration
└── package.json      # Dependencies and scripts
```

## Configuration

### API Base URL

The API base URL is configured in `src/api/client.js`. In development, it uses Vite's proxy (configured in `vite.config.js`). In production, it should point to your API server.

### Environment Variables

You can use environment variables by prefixing them with `VITE_`:

```bash
VITE_API_BASE_URL=https://api.example.com
```

Access in code:
```javascript
import.meta.env.VITE_API_BASE_URL
```

## Troubleshooting

### Build Fails

```bash
# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install
```

### Deprecation Warnings

These are normal and don't affect functionality. They'll be resolved as dependencies update.

### ESLint Errors

```bash
# Auto-fix where possible
npm run lint
```

