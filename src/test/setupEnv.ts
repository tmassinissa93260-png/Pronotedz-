// Charge en premier (via --require) pour garantir que le client SQLite est
// initialise sur une base en memoire avant que le moindre module de test ne
// l'importe indirectement (store, agent, seed...).
process.env.DATABASE_PATH = ":memory:";
