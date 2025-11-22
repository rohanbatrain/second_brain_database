export interface Deck {
    _id: string;
    title: string;
    created_at: string;
}

export interface Card {
    _id: string;
    deck_id: string;
    front_content: string;
    back_content: string;
    next_review_date: string;
    interval: number;
    ease_factor: number;
    repetition_count: number;
}

export interface ReviewRequest {
    rating: number;
}
