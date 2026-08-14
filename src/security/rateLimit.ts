import { RequestHandler } from "express";

// Limiteur en memoire, simple et suffisant pour un seul processus (pas de
// dependance externe). Fenetre glissante approximative par compteur fixe.
// A remplacer par une solution partagee (Redis) en cas de deploiement multi-instance.
export function rateLimit(options: { windowMs: number; max: number }): RequestHandler {
  const hits = new Map<string, { count: number; resetAt: number }>();

  return (req, res, next) => {
    const key = req.ip || "unknown";
    const now = Date.now();
    const entry = hits.get(key);

    if (!entry || now > entry.resetAt) {
      hits.set(key, { count: 1, resetAt: now + options.windowMs });
      return next();
    }

    entry.count += 1;
    if (entry.count > options.max) {
      res.status(429).json({ error: "Trop de requetes, merci de reessayer dans un instant." });
      return;
    }
    next();
  };
}
