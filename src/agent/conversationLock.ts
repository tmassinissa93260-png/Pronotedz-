// Serialise les traitements concurrents d'une meme conversation (meme canal +
// meme utilisateur externe + meme commerce). Sans ce verrou, deux requetes
// simultanees pour la meme conversation (double-clic client, retry reseau,
// webhook renvoye avant la fin du traitement precedent) liraient le meme
// historique, lanceraient deux appels LLM independants et ecraseraient
// l'historique de l'autre (last-write-wins), avec un risque de double
// execution d'outils (double reservation/commande).
const chains = new Map<string, Promise<unknown>>();

export function conversationKey(channel: string, externalUserId: string, businessId: string): string {
  return `${channel}:${externalUserId}:${businessId}`;
}

export function withConversationLock<T>(key: string, fn: () => Promise<T>): Promise<T> {
  const previous = chains.get(key) ?? Promise.resolve();
  const run = previous.then(fn, fn);
  // On ignore les rejets dans la chaine partagee pour ne pas bloquer les
  // appels suivants ; l'appelant recoit toujours le vrai resultat/erreur via `run`.
  chains.set(
    key,
    run.catch(() => undefined)
  );
  return run;
}
