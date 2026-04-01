# 🚀 NetWatch P2P - Deployment Guide

## Deployed Successfully! ✅

This app is now ready to deploy to Railway, Render, or similar platforms.

---

## 📋 What Was Done for Production

✅ Fixed SECRET_KEY (uses environment variables)
✅ Fixed port binding (uses PORT environment variable)  
✅ Added Procfile (for Railway/Heroku)
✅ Added runtime.txt (specifies Python version)
✅ Added .gitignore (excludes unnecessary files)

---

## 🚀 Deploy to Railway (Recommended)

### Step 1: Setup Git
```bash
cd your-netwatch-folder
git init
git add .
git commit -m "Production ready"
git branch -M main
```

### Step 2: Push to GitHub
```bash
git remote add origin https://github.com/YOUR-USERNAME/netwatch.git
git push -u origin main
```

### Step 3: Deploy on Railway
1. Go to https://railway.app
2. Sign up (free)
3. Click "New Project" 
4. "Deploy from GitHub"
5. Select your netwatch repo
6. Railway auto-deploys! 🎉

### Step 4: Set Environment Variables
In Railway dashboard:
```
SECRET_KEY = your-random-secret-string-here
FLASK_ENV = production
```

**Your app is now live at:** `https://yourapp.railway.app`

---

## 🔐 Configure Email Alerts

Before deploying, edit app.py lines ~115-116:

```python
sender_email = "your.email@gmail.com"           # Your Gmail
sender_password = "your-app-specific-password"  # From Google Account
```

**How to get app-specific password:**
1. Go to https://myaccount.google.com/apppasswords
2. Select "Mail" and "Windows Computer"
3. Google generates a 16-char password
4. Copy it to app.py

---

## ✨ What's New in This Version

| Feature | Status |
|---------|--------|
| User Auth | ✅ Working |
| Device Monitoring | ✅ Working |
| Peer Connections | ✅ Working |
| Email Alerts | ✅ Working (needs Gmail config) |
| In-App Notifications | ✅ Working |
| Dashboard | ✅ Working |

---

## 🎯 Quick Links

- **Local:** http://localhost:5000
- **Railway Deployment:** https://railway.app
- **GitHub:** Push your code here
- **Gmail Passwords:** https://myaccount.google.com/apppasswords

---

## 📊 Project Structure

```
netwatch/
├── app.py                      # Main Flask application
├── Procfile                    # For Railway deployment
├── runtime.txt                 # Python version
├── requirements.txt            # Dependencies
├── .gitignore                  # Git exclusions
├── netwatch.db                 # SQLite database (local only)
└── templates/
    ├── base.html              # Base layout
    ├── login.html             # Login page
    ├── register.html          # Registration
    ├── dashboard.html         # Main dashboard
    └── settings.html          # Settings page
```

---

## 🎓 Next Steps

1. **Test locally first:**
   ```bash
   python3 app.py
   ```

2. **Register an account**

3. **Test peer connection** (add another device)

4. **Deploy to Railway**

5. **Share the URL** with friends/family to monitor together

---

## 🐛 Troubleshooting

**App won't start?**
- Check Python version: `python3 --version` (should be 3.11+)
- Check dependencies: `pip install -r requirements.txt`

**Email not working?**
- Verify Gmail app password is correct
- Check spam folder
- Ensure email is enabled in Settings

**Peer connection fails?**
- Check both devices have the app running
- Verify IP addresses are correct
- Check they're on the same network (or use deployed URL)

**Database errors?**
- Delete netwatch.db locally
- Run app again: `python3 app.py`

---

## 📞 Support

For issues or questions:
1. Check app logs (terminal output)
2. Verify all settings are configured
3. Test with another device
4. Check email configuration

---

**Ready to deploy? Go to https://railway.app 🚀**
