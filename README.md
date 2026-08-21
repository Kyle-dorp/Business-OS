# Business-EOS

A **beautiful, open, spacious SaaS platform** for small business management. Multi-tenant, feature-rich, production-ready.

## ✨ Features

### Core Modules
- **Scheduling** - AI-powered staff scheduling
- **Booking** - Public booking integration
- **Customers & CRM** - Full customer management with loyalty tracking
- **Inventory** - Stock tracking and reorder management
- **Invoicing** - Invoice creation and payment tracking
- **Payroll** - Payroll processing and tax compliance
- **Team Chat** - Internal communication and shift notes
- **Analytics** - Business metrics and forecasting
- **Accounting** - Chart of accounts, expenses, bills

### Design Philosophy
- **Spacious**: Generous whitespace, never feels crowded
- **Clean**: Minimal, intentional interface
- **Modern**: Beautiful colors, smooth animations
- **Responsive**: Perfect on mobile, tablet, desktop
- **Fast**: Snappy API, optimized frontend

## 🚀 Quick Start

### Prerequisites
- Node.js 18+
- Python 3.11+
- PostgreSQL 13+

### Local Development

```bash
# Clone repository
git clone <repo-url>
cd business-eos

# Setup backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Setup database
createdb business_eos
export DATABASE_URL="postgresql://localhost/business_eos"
export SECRET_KEY="dev-secret-key"

# Run backend
uvicorn app.main:app --reload

# In new terminal, setup frontend
cd frontend
npm install
npm run dev

# Visit http://localhost:5173
```

### Default Login
When you first run the app, it will ask you to set up the initial manager account.

## 📁 Project Structure

```
business-eos/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app
│   │   ├── models.py            # Database models
│   │   ├── auth.py              # Authentication
│   │   ├── routers.py           # API routers for new modules
│   │   ├── modules/             # Feature modules
│   │   │   ├── inventory.py
│   │   │   ├── customers.py
│   │   │   ├── invoicing.py
│   │   │   ├── payroll.py
│   │   │   ├── team_communication.py
│   │   │   └── analytics.py
│   │   ├── database.py
│   │   ├── tenancy.py           # Multi-tenant support
│   │   └── stripe_service.py
│   ├── pyproject.toml
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/               # Route pages
│   │   │   ├── Login.tsx
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Customers.tsx
│   │   │   ├── Inventory.tsx
│   │   │   ├── Invoicing.tsx
│   │   │   ├── Payroll.tsx
│   │   │   ├── TeamChat.tsx
│   │   │   └── Analytics.tsx
│   │   ├── components/          # UI components
│   │   │   ├── Button.tsx
│   │   │   ├── Input.tsx
│   │   │   └── Card.tsx
│   │   ├── hooks/
│   │   │   └── useApi.ts        # API client
│   │   ├── stores/
│   │   │   └── auth.ts          # Auth state
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── tsconfig.json
├── Dockerfile                   # Docker build
├── DEPLOYMENT.md               # Railway deployment guide
├── FRONTEND_DESIGN.md          # Design system specification
├── BUSINESS-EOS-STRATEGY.md    # Business strategy
└── IMPLEMENTATION_ROADMAP.md   # Development roadmap
```

## 🏗️ Architecture

### Backend (FastAPI + PostgreSQL)
- Multi-tenant architecture
- Role-based access control
- RESTful API design
- Stripe integration for billing
- AI-powered features (scheduling)

### Frontend (React 18 + TypeScript)
- Modern component architecture
- Zustand state management
- TanStack Query for data
- Tailwind CSS design system
- Responsive layouts

### Database (PostgreSQL)
- SQLModel ORM
- Tenant isolation via business_id
- Full audit trail for all changes
- Automatic migrations on startup

## 🔐 Security

- JWT token authentication
- Multi-tenant data isolation
- Password hashing with bcrypt
- CORS protection
- SQL injection prevention (ORM)
- XSS protection (React)

## 📊 API Documentation

Visit `http://localhost:8000/docs` for interactive API docs (Swagger UI)

### Authentication
```bash
# Login
POST /auth/login
Content-Type: application/json

{
  "username": "manager",
  "password": "password"
}

# Response includes token
# Use in subsequent requests:
Authorization: Bearer {token}
```

### Business Isolation
All endpoints require `X-Business-Id` header:
```bash
X-Business-Id: 1
```

## 💰 Pricing & Features

### Starter ($10/mo)
- Scheduling
- Basic booking
- Up to 5 staff

### Professional ($49/mo)
- Everything in Starter
- Full CRM + customers
- Invoicing
- Analytics
- Unlimited staff

### Business ($129/mo)
- Everything in Professional
- Payroll processing
- Inventory management
- Team chat & collaboration
- Advanced reports

### Enterprise (Custom)
- All features
- Custom branding
- Priority support
- SLA guarantee

## 🚀 Deployment

### Railway (Recommended)
1 click deploy with automatic PostgreSQL:
```bash
railway link
railway up
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed instructions.

### Other Platforms
Works on any platform supporting:
- Docker
- PostgreSQL
- Node.js 18+
- Python 3.11+

## 🧪 Testing

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test
```

## 🐛 Bug Reports

Found a bug? Create an issue with:
- Steps to reproduce
- Expected behavior
- Actual behavior
- Screenshots if applicable

## 📝 License

Licensed under MIT License. See LICENSE file for details.

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📞 Support

### Documentation
- API Docs: `/docs` (Swagger)
- Design System: `FRONTEND_DESIGN.md`
- Deployment: `DEPLOYMENT.md`
- Strategy: `BUSINESS-EOS-STRATEGY.md`
- Roadmap: `IMPLEMENTATION_ROADMAP.md`

### Need Help?
- Check existing issues on GitHub
- Read the deployment guide
- Review API documentation

---

**Built with ❤️ for beautiful business software**
