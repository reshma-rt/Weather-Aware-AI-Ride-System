
(function () {
    'use strict';

    if (window.__movioSavedBookingFix) return;
    window.__movioSavedBookingFix = true;

    const allowed = new Set([
        'scheduled',
        'requested',
        'accepted',
        'arriving',
        'in_progress',
        'needs_location'
    ]);

    async function ownedRides() {
        const data = await api('/rides', {cache: 'no-store'});

        if (!Array.isArray(data.rides)) {
            throw Error('Unable to load your bookings.');
        }

        return data.rides;
    }

    async function ownedRide(id) {
        const ride = (await ownedRides()).find(
            r => Number(r.id) === Number(id)
        );

        if (!ride) {
            throw Error(
                'Booking #' + id +
                ' was not found in this signed-in account.'
            );
        }

        return ride;
    }

    voiceRides = async () => {
        return (await ownedRides()).filter(
            r => allowed.has(r.status)
        );
    };

    const previousPost = post;

    post = async function (path, data) {
        const match = /^\/rides\/(\d+)\/status$/.exec(path);

        if (match && data?.status === 'cancelled') {
            const id = Number(match[1]);
            const ride = await ownedRide(id);

            if (ride.status !== 'cancelled') {
                if (ride.status === 'scheduled') {
                    try {
                        await previousPost(
                            '/weather-booking/cancel',
                            {ride_id: id}
                        );
                    } catch (error) {
                        // Dispatch might occur while cancellation is sent.
                        const latest = await ownedRide(id);

                        if (latest.status === 'scheduled') {
                            throw error;
                        }

                        if (latest.status !== 'cancelled') {
                            await previousPost(path, data);
                        }
                    }
                } else {
                    await previousPost(path, data);
                }
            }

            const saved = await ownedRide(id);

            if (saved.status !== 'cancelled') {
                throw Error(
                    'Cancellation was not saved. Please retry.'
                );
            }

            return {ok: true, id};
        }

        const result = await previousPost(path, data);

        if (
            (path === '/rides' ||
             path === '/weather-booking/commit') &&
            result.id
        ) {
            await ownedRide(result.id);
        }

        return result;
    };

    const previousHandler = handleMovioVoiceMessage;
    const pending = new Map();

    handleMovioVoiceMessage = async function (message) {
        if (
            !message ||
            message.channel !== 'ai-ride-call' ||
            message.nonce !== aiNonce
        ) {
            return;
        }

        if (message.type === 'booking_saved') {
            try {
                await ownedRide(message.id);
            } catch (error) {
                toast(error.message);
                return;
            }
        }

        if (
            message.type === 'action' &&
            message.action?.type === 'cancel' &&
            message.action.request_id
        ) {
            const key = aiNonce + ':' + message.action.request_id;

            if (!pending.has(key)) {
                pending.set(
                    key,
                    Promise.resolve().then(
                        () => previousHandler(message)
                    )
                );
            }

            return pending.get(key);
        }

        return previousHandler(message);
    };

    renderVoiceHistory();
    refreshRides();
})();
